"""The one place this server depends on how the MCP SDK is built inside.

Two kinds of dependency live here, and nowhere else:

**The tool registry.** ``MCPServer`` publishes no API for what a fleet-wide
post-registration pass needs — enumerating the registered tools, rewrapping a
tool's function, rewriting a published schema. Those passes reach through
``mcp._tool_manager._tools``, a name with no compatibility promise.

**Request routing.** ``MCPServer``'s request handlers do not do the work
themselves; they call back into the server's own public methods —
``tools/call`` runs ``self.call_tool(...)``, ``tools/list`` runs
``self.list_tools()``, and so on. Replacing one of those methods on the
*instance* therefore changes what every request does, without touching a
private name. But that routing is an implementation fact, not a promise, so it
is relied on from this one module and pinned by a test that goes through the
real request path.

This module exists because those reaches used to be spread across eleven call
sites, each with its own copy of the same coercion dance — eleven chances for
an upgrade to miss one, silently, where no type checker looks. It earned its
keep on the port to mcp 2.x: the SDK renamed its low-level server and deleted
the handshake-version hack, and the change landed here and in the entrypoint
rather than across the codebase. ``tests/unit/test_sdk_seam_is_exclusive.py``
fails if any other module names an SDK private again.

The seam deliberately does NOT import the SDK. Its parameters are typed ``Any``
because the only thing it knows about *mcp* is the shape of what it reaches
for — which is exactly the knowledge being quarantined. That also keeps the
SDK's import cost off this module, which matters to ``__main__``'s fast path.

What it hands back is PUBLIC: ``Tool.name`` / ``.title`` / ``.fn`` /
``.meta`` / ``.parameters`` / ``.output_schema`` are documented attributes of
the SDK's tool object. Callers keep operating on them directly, so each pass's
own logic stays where it belongs. Only the *path* is privileged.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any, Final, Protocol


class RegisteredTool(Protocol):
    """A registered tool, narrowed to the fields this server reads or writes.

    A structural stand-in for ``mcp.server.mcpserver.tools.base.Tool``, declared
    rather than imported so the seam stays SDK-import-free (see the module
    docstring) — and so the exact surface this server depends on is written
    down in one place instead of being implied by scattered attribute access.

    Every field here is public SDK API, so an upgrade has only to confirm these
    eight names survive. ``fn_metadata`` and ``annotations`` are deliberately
    ``Any``: the output-schema parity check reads ``fn_metadata.output_model``
    and the client-hints pass reads ``annotations.destructive_hint``, but nothing
    here should grow an opinion about the SDK's own types. ``meta`` is what the
    SDK publishes as the tool's ``_meta`` in ``tools/list``.
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
    annotations: Any
    meta: dict[str, Any] | None
    parameters: dict[str, Any]
    output_schema: dict[str, Any] | None


#: One of ``MCPServer``'s public async methods (``call_tool``, ``list_tools``, …).
ServerMethod = Callable[..., Awaitable[Any]]

#: The dispatch entry point: ``MCPServer.call_tool``.
DispatchFn = ServerMethod

#: The public methods ``MCPServer``'s request handlers route through, one per
#: kind of request a client can make for tools, prompts and resources. Gating
#: all of them is how the entrypoint keeps a client from being answered out of
#: a registry that is still loading.
REQUEST_METHODS: Final[tuple[str, ...]] = (
    "list_tools",
    "call_tool",
    "list_prompts",
    "get_prompt",
    "list_resources",
    "list_resource_templates",
    "read_resource",
)


def _tool_manager(mcp: Any) -> Any:
    """The server's ``ToolManager``. Private attribute — no stability promise."""

    return mcp._tool_manager


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


def wrap_server_method(mcp: Any, name: str, wrap: Callable[[ServerMethod], ServerMethod]) -> None:
    """Interpose *wrap* around one of the server's public async methods.

    The replacement is installed on this INSTANCE, so it applies to everything
    that reaches the server — a request off the wire (the SDK's handlers call
    ``self.<name>(...)``) and a direct in-process call alike — and to no other
    server in the process.

    *wrap* receives the current method and returns its replacement;
    ``functools.wraps`` is applied here so callers need not repeat it. Called
    more than once on the same method, the interpositions stack, outermost
    last.

    Construction time only, never per request.
    """

    original: ServerMethod = getattr(mcp, name)
    setattr(mcp, name, functools.wraps(original)(wrap(original)))


def wrap_dispatch(mcp: Any, wrap: Callable[[DispatchFn], DispatchFn]) -> None:
    """Interpose *wrap* around tool dispatch (``MCPServer.call_tool``).

    This sits OUTSIDE ``Tool.run``, which is what lets it reject a call before
    any tool runs, rewrite a result after the SDK has built it, and undo the
    prose preamble ``Tool.run`` puts on every ``ToolError``.
    """

    wrap_server_method(mcp, "call_tool", wrap)
