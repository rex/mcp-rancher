"""The one place this server touches the MCP SDK's private internals.

FastMCP exposes no public API for the things a fleet-wide post-registration
pass needs: enumerating the registered tools, rewriting a published schema,
interposing on dispatch, or stamping the handshake version. Every such pass
therefore reaches through ``mcp._tool_manager._tools`` or ``mcp._mcp_server``
— names carrying no compatibility promise, which the SDK may rename in any
release and which mcp 2.0.0 in fact does rename (``_mcp_server`` becomes
``_lowlevel_server``).

Before this module those reaches were spread across eleven call sites, each
carrying its own copy of the same ``Any``-coercion dance and its own comment
re-explaining the same escape hatch — eleven independent chances for a port to
miss one, silently, in a place no type checker looks. Consolidating them here
makes the SDK upgrade a rewrite of ONE module plus a mechanical import swap,
and turns "did we miss one?" into a question a test can answer:
``tests/unit/test_sdk_seam_is_exclusive.py`` fails if any other module under
``src/`` or ``devtools/`` names an SDK private again.

The seam deliberately does NOT import the SDK. Its parameters are typed
``Any`` because the only thing it knows about *mcp* is the shape of the
private attributes it reaches for — which is exactly the knowledge being
quarantined. Typing the parameter ``Any`` from the outset is also what retires
the two-step coercion the old call sites needed to keep pyright strict's
``reportPrivateUsage`` quiet. As a bonus it keeps the ~1.5 s
``mcp.server.fastmcp`` import off this module, which matters to ``__main__``'s
two-phase startup.

What the seam hands back is PUBLIC: ``Tool.name`` / ``.title`` / ``.fn`` /
``.parameters`` / ``.output_schema`` are documented attributes of the SDK's
tool object. Callers keep operating on them directly, so each pass's own logic
stays where it belongs. Only the *path* to those objects is privileged, and
only that path lives here.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any, Protocol


class RegisteredTool(Protocol):
    """A registered tool, narrowed to the fields this server reads or writes.

    A structural stand-in for ``mcp.server.fastmcp.tools.base.Tool``, declared
    rather than imported so the seam stays SDK-import-free (see the module
    docstring) — and so the exact surface this server depends on is written
    down in one place instead of being implied by scattered attribute access.

    Every field here is public SDK API, so a port has only to confirm these
    six names survive. ``fn_metadata`` is deliberately ``Any``: the output-schema
    parity check reads ``fn_metadata.output_model`` off it, but nothing here
    should grow an opinion about the SDK's own metadata type.
    ``output_schema`` is a ``functools.cached_property`` on
    the real class rather than a model field; assigning it (as schema
    compaction does) populates the cache, which is what makes the published
    schema a dial without disturbing ``fn_metadata`` — and therefore without
    disturbing ``structuredContent``.
    """

    name: str
    title: str | None
    fn: Callable[..., Any]
    fn_metadata: Any
    parameters: dict[str, Any]
    output_schema: dict[str, Any] | None


#: The tool manager's dispatch entry point (``ToolManager.call_tool``).
DispatchFn = Callable[..., Awaitable[Any]]


def _tool_manager(mcp: Any) -> Any:
    """FastMCP's ``ToolManager``. Private attribute — no stability promise."""

    return mcp._tool_manager


def _lowlevel_server(mcp: Any) -> Any:
    """The low-level ``Server`` FastMCP wraps.

    Private attribute, and the one the SDK actually renames: mcp 2.0.0 calls
    it ``_lowlevel_server``.
    """

    return mcp._mcp_server


def registered_tools(mcp: Any) -> list[RegisteredTool]:
    """Every currently-registered tool object.

    A snapshot list, not the live ``dict.values()`` view: callers iterate this
    while mutating the tools it contains, and a snapshot means a future caller
    that also adds or removes a tool mid-pass gets a coherent result instead of
    a "dictionary changed size during iteration". The objects are the real
    ones, so mutations through them still land on the registry.
    """

    tools: dict[str, RegisteredTool] = _tool_manager(mcp)._tools
    return list(tools.values())


def registered_tool_names(mcp: Any) -> frozenset[str]:
    """The names of every currently-registered tool.

    Used to diff the registry before and after a family registrar runs, which
    is how each tool learns which family it belongs to.
    """

    tools: dict[str, RegisteredTool] = _tool_manager(mcp)._tools
    return frozenset(tools)


def is_registered(mcp: Any, name: str) -> bool:
    """Whether *name* is registered right now.

    Re-reads the registry rather than closing over a snapshot: the toolset
    dispatch gate calls this per request, and its whole job is to distinguish
    a tool that was *removed* by the active profile from one that never
    existed.
    """

    tools: dict[str, RegisteredTool] = _tool_manager(mcp)._tools
    return name in tools


def wrap_dispatch(mcp: Any, wrap: Callable[[DispatchFn], DispatchFn]) -> None:
    """Interpose *wrap* around the tool manager's dispatch entry point.

    ``ToolManager.call_tool`` sits OUTSIDE ``Tool.run``, which is what makes it
    the only seam that can reject a call before dispatch, and the only one that
    can undo the prose preamble ``Tool.run`` puts on every ``ToolError``.

    *wrap* receives the current dispatch callable and returns its replacement;
    ``functools.wraps`` is applied here so callers don't each repeat it. Called
    more than once, the interpositions stack — outermost last, exactly as the
    raw monkeypatches did.

    Construction time only, never per request.
    """

    manager = _tool_manager(mcp)
    original: DispatchFn = manager.call_tool
    manager.call_tool = functools.wraps(original)(wrap(original))


def stamp_server_version(mcp: Any, version: str) -> None:
    """Set the version reported as ``serverInfo.version`` in the handshake.

    ``FastMCP.__init__`` accepts no ``version``, so it builds the low-level
    ``Server`` with ``version=None`` and the SDK falls back to
    ``pkg_version("mcp")`` — telling every client the *SDK's* version instead
    of ours. Assigning the attribute is the only seam v1 exposes. (mcp 2.0.0
    takes ``version=`` on the constructor, so the port deletes this rather
    than porting it.)
    """

    _lowlevel_server(mcp).version = version


def advertised_server_version(mcp: Any) -> str:
    """The version a client would actually be told during the handshake.

    The read that pairs with :func:`stamp_server_version`. It goes through
    ``create_initialization_options()`` rather than reading the attribute back,
    so it proves what reaches the wire rather than merely that an assignment
    happened.
    """

    options: Any = _lowlevel_server(mcp).create_initialization_options()
    version: str = options.server_version
    return version


def install_list_tools_handler(mcp: Any, handler: Callable[[], Awaitable[Any]]) -> None:
    """Replace the low-level ``tools/list`` request handler with *handler*.

    The low-level server keeps its handlers in a dict keyed by request type;
    re-invoking its ``list_tools()`` decorator overwrites the entry FastMCP
    installed. Used by the two-phase startup to defer ``tools/list`` until the
    background tool-loading thread has finished.
    """

    _lowlevel_server(mcp).list_tools()(handler)


def installed_list_tools_handler(mcp: Any) -> Any:
    """The handler currently answering ``tools/list``, or ``None``.

    The read that pairs with :func:`install_list_tools_handler`. Two-phase
    startup is correct only if the install actually DISPLACES the handler
    FastMCP registered at construction — a silent no-op there would mean
    ``tools/list`` racing the background tool loader and answering with a
    partial registry, which is the exact failure the two-phase design exists
    to prevent. This is how that is checked without a second module having to
    learn where the low-level server keeps its handlers.

    Matched on the request type's name rather than by importing
    ``mcp.types.ListToolsRequest``, so the seam stays SDK-import-free.
    """

    handlers: dict[Any, Any] = _lowlevel_server(mcp).request_handlers
    for request_type, handler in handlers.items():
        if request_type.__name__ == "ListToolsRequest":
            return handler
    return None
