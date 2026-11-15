"""MCP server construction."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer


def new_server(name: str, instructions: str) -> MCPServer:
    """A bare server that reports OUR version, with nothing registered on it.

    The one place a server is constructed for real use, so the version cannot
    be forgotten at a second call site. Left to itself the SDK reports *its
    own* package version as ``serverInfo.version`` — a number that only moves
    when the SDK is upgraded, which once left an operator restarting the server
    mid-incident with no way to confirm the restart had picked up a fix.

    Deliberately takes plain strings rather than settings: the entrypoint
    builds the server before tools load, and tests build one with no Rancher
    configured at all. Guarded by ``tests/unit/test_server_version.py``.
    """

    from rancher_mcp import __version__

    return MCPServer(name=name, instructions=instructions, version=__version__)


#: How long a request waits for the registry before the server admits it is
#: not going to be ready. Generous on purpose: a loader that FAILS exits the
#: process, so reaching this means startup is merely slow, not broken.
REGISTRY_WAIT_SECONDS = 30.0


def hold_requests_until(
    mcp: MCPServer, ready: threading.Event, *, timeout: float = REGISTRY_WAIT_SECONDS
) -> None:
    """Make every request that reads the registry wait until *ready* is set.

    The entrypoint starts serving before the tool modules have loaded, so that
    a client's first message is answered inside its deadline. That first
    message needs only the server's identity. Everything after it reads the
    registry, and must not be answered from one that is still being built.

    *All* of those requests are held, not just ``tools/list``:

    * a client lists prompts and resources in parallel with tools, straight
      after connecting — holding only tools would hand it an empty prompt list
      that it has no reason to ask for again;
    * the protocol is stateless, so a resumed session can call a tool before
      it has listed anything.

    If *ready* is not set within *timeout* the request fails with a protocol
    error rather than being answered from a partial registry: an empty or
    truncated list is a wrong answer that looks like a right one, and a client
    may cache it.
    """

    from anyio import to_thread
    from mcp.shared.exceptions import MCPError
    from mcp.types import INTERNAL_ERROR

    from rancher_mcp.sdk_registry import REQUEST_METHODS, ServerMethod, wrap_server_method

    def hold(name: str) -> Callable[[ServerMethod], ServerMethod]:
        def wrap(method: ServerMethod) -> ServerMethod:
            async def held(*args: Any, **kwargs: Any) -> Any:
                if ready.is_set():
                    return await method(*args, **kwargs)
                became_ready = await to_thread.run_sync(
                    lambda: ready.wait(timeout=timeout), abandon_on_cancel=True
                )
                if not became_ready:
                    raise MCPError(
                        code=INTERNAL_ERROR,
                        message=(
                            f"rancher-mcp is still registering its tools after {timeout:g} s; "
                            "retry shortly"
                        ),
                    )
                # Loading stacks further passes on top of this one — the toolset
                # gate, the JSON error envelope, compact text. A request parked
                # here came in before they existed, so `method` is stale for
                # it. Go back in through the server's CURRENT method: that runs
                # whatever loading installed, then falls straight through this
                # hold now that the flag is set.
                current: ServerMethod = getattr(mcp, name)
                return await current(*args, **kwargs)

            return held

        return wrap

    for name in REQUEST_METHODS:
        wrap_server_method(mcp, name, hold(name))


def register_all_tools(mcp: MCPServer) -> None:
    """Import and register every tool module on *mcp*.

    All tool-module imports are deferred until this function is called so that
    ``import rancher_mcp.server`` is cheap.  In production ``__main__.main()``
    calls this from a background thread, so the client's first request — the
    ``server/discover`` probe, or a legacy ``initialize`` — is answered before
    the heavy imports begin.
    """
    # Local imports are intentional: keep module-level import cost near-zero.
    from rancher_mcp.audit import apply_sensitive_reveal_audit
    from rancher_mcp.metrics import apply_metrics_to_all_tools
    from rancher_mcp.tools.mcp_prompts import register_mcp_prompts
    from rancher_mcp.tools.mcp_resources import register_mcp_resources
    from rancher_mcp.tools.support.capability_unavailable import (
        apply_capability_unavailable_translation,
    )
    from rancher_mcp.tools.support.errors import (
        apply_bare_json_errors,
        apply_structured_errors_to_all_tools,
    )
    from rancher_mcp.tools.support.toolset_gate import apply_toolset_filter
    from rancher_mcp.toolsets import register_families

    # `register_families` calls every family's `register_*_tools(mcp)` — the
    # toolset profile -> function mapping lives in ONE place, `toolsets.py`
    # (design requirement, and see that module's docstring for why). Every
    # tool is registered unconditionally, exactly as before; `apply_toolset_filter`
    # then resolves RANCHER_TOOLSETS/RANCHER_TOOLS/RANCHER_EXCLUDE_TOOLS and
    # deregisters whatever the active profile doesn't want — BEFORE any of the
    # passes below, so all of them (next-steps targets, titles, schema
    # compaction, the apply_* wrapper chain) only ever see the active surface.
    registration = register_families(mcp)
    apply_toolset_filter(mcp, registration)
    register_mcp_resources(mcp)
    register_mcp_prompts(mcp)
    # Every pack is registered (and the toolset profile applied) now, so the
    # tool manager's schemas are final: populate the next-steps target
    # registry (models/base.py's `next_steps` computed field queries this to
    # avoid forwarding a scope key — cluster_id/namespace — to a suggested
    # tool that doesn't actually accept it, AND to drop a suggestion whose
    # tool isn't in the active profile at all).
    # The SDK publishes no API for enumerating what is registered, so every
    # pass here goes through `rancher_mcp.sdk_registry` — the one module that
    # is allowed to reach into the SDK's internals, and the one place a future
    # SDK upgrade has to touch (gated by test_sdk_seam_is_exclusive.py).
    from rancher_mcp.next_step_targets import populate_from_tools, reset_tool_parameters
    from rancher_mcp.sdk_registry import registered_tools

    # Reset first: this function can run more than once per PROCESS (never
    # per server — every test file that builds its own server + calls this
    # again is a second build in the same process), and the registry must
    # reflect only the registry just built, not a stale union with whatever a
    # previous, differently-profiled build left behind.
    reset_tool_parameters()
    populate_from_tools(registered_tools(mcp))
    # Human-readable `title` on every tool (a data field, not a wrapping
    # pass — order relative to the apply_* chain below doesn't matter).
    from rancher_mcp.tools.support.titles import apply_titles_to_all_tools

    apply_titles_to_all_tools(mcp)
    # Also a data pass, not a wrapper: rewrites the PUBLISHED output schemas
    # (64% of the tools/list payload) to drop Pydantic scaffolding and to repair
    # the next-steps contract, which named a field no response carries and
    # omitted the one every response does. `structuredContent` is unaffected.
    from rancher_mcp.schema_compaction import apply_compact_output_schemas

    apply_compact_output_schemas(mcp)
    # A third data pass: client hints carried in each tool's `_meta`. Claude
    # Code defers every tool definition behind tool search by default, so one
    # marks the handful of front-door tools to load upfront instead; the other
    # makes it put a person in front of every destructive call, in any
    # permission mode — which a model-supplied confirmation phrase cannot do.
    from rancher_mcp.tools.support.client_hints import (
        apply_always_load,
        apply_requires_user_interaction,
    )

    apply_always_load(mcp)
    apply_requires_user_interaction(mcp)
    # Order (each apply wraps the previous, so the LAST is outermost at call time):
    # sensitive-reveal audit is INNERMOST (M-SEC) — it wraps the impl and emits an
    # audit record on the raw successful reveal; capability-unavailable translation
    # (M-A11/K-8b) turns a 404'd optional-app list into RancherCapabilityError next;
    # metrics records the translated error_code; structured_errors is OUTERMOST and
    # translates whatever RancherMCPError survives to a ToolError at the MCP boundary.
    apply_sensitive_reveal_audit(mcp)
    apply_capability_unavailable_translation(mcp)
    apply_metrics_to_all_tools(mcp)
    apply_structured_errors_to_all_tools(mcp)
    # The two below are not tool wrappers: they interpose on DISPATCH, so they
    # sit outside even `Tool.run`. Text compaction has to live there because the
    # text block it rewrites does not exist until the SDK converts the tool's
    # return value, after every wrapper above has already returned.
    from rancher_mcp.result_compaction import apply_compact_result_text

    apply_compact_result_text(mcp)
    # Outermost: the only place we can undo the SDK's prose preamble and
    # guarantee every emitted error is valid JSON (AE-03).
    apply_bare_json_errors(mcp)


def create_mcp_server() -> MCPServer:
    """Create a fully-configured server (tools eager-loaded).

    Intended for tests and one-off scripts.  Production startup uses
    ``register_all_tools`` from a background thread instead.
    """
    from rancher_mcp.config import get_settings

    settings = get_settings()
    mcp = new_server(settings.server_name, settings.server_instructions)
    register_all_tools(mcp)
    return mcp
