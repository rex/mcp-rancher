"""FastMCP server construction."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register_all_tools(mcp: FastMCP) -> None:
    """Import and register every tool module on *mcp*.

    All tool-module imports are deferred until this function is called so that
    ``import rancher_mcp.server`` is cheap.  In production ``__main__.main()``
    calls this from a background thread, allowing the MCP ``initialize``
    handshake to complete before the heavy imports begin.
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
    # FastMCP publishes no API for enumerating what is registered, so every
    # pass here goes through `rancher_mcp.sdk_registry` — the one module that
    # is allowed to reach into the SDK's internals, and the one place a future
    # SDK upgrade has to touch (gated by test_sdk_seam_is_exclusive.py).
    from rancher_mcp.next_step_targets import populate_from_tools, reset_tool_parameters
    from rancher_mcp.sdk_registry import registered_tools

    # Reset first: this function can run more than once per PROCESS (never
    # per server — every test file that builds its own FastMCP + calls this
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
    # Not a tool wrapper: patches the tool MANAGER, so it sits outside even
    # `Tool.run` — the only place we can undo the SDK's prose preamble and
    # guarantee every emitted error is valid JSON (AE-03).
    apply_bare_json_errors(mcp)


def stamp_server_version(mcp: FastMCP) -> None:
    """Advertise *our* version as ``serverInfo.version`` in the MCP handshake.

    Without this the SDK reports *its own* version, so ours never moved when
    we shipped: an operator restarting the server mid-incident had no way to
    confirm the restart had picked up a fix. The mechanism lives in
    ``rancher_mcp.sdk_registry.stamp_server_version``; this wrapper exists so
    both entrypoints (``__main__.main`` and ``create_mcp_server``) can stamp
    the version without either of them having to know what our version is.

    Guarded by ``tests/unit/test_server_version.py``.
    """
    # Local imports: keep this module's import cost near-zero (see above).
    from rancher_mcp import __version__, sdk_registry

    sdk_registry.stamp_server_version(mcp, __version__)


def create_mcp_server() -> FastMCP:
    """Create a fully-configured FastMCP server (tools eager-loaded).

    Intended for tests and one-off scripts.  Production startup uses
    ``register_all_tools`` from a background thread instead.
    """
    from rancher_mcp.config import get_settings

    settings = get_settings()
    mcp = FastMCP(
        name=settings.server_name,
        instructions=settings.server_instructions,
    )
    stamp_server_version(mcp)
    register_all_tools(mcp)
    return mcp
