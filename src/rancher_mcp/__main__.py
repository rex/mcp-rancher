"""CLI entrypoint.

Startup strategy
----------------
``from mcp.server.fastmcp import FastMCP`` alone takes ~1.5-2 s on this
machine.  Loading all 100+ tool modules on top pushes total startup past the
~3 s threshold at which Claude Code gives up waiting for the MCP
``initialize`` response.

To fix this we split startup into two phases that run concurrently:

Phase A (main thread, ~2 s total):
    1. Import lightweight config/logging/catalog modules.
    2. Validate settings and configure logging.
    3. Import FastMCP and create a bare server instance.
    4. Kick off Phase B in a daemon thread.
    5. Override ``list_tools`` so it blocks until Phase B finishes.
    6. Call ``mcp.run()`` — the event loop starts and responds to
       ``initialize`` immediately (well under the 3 s deadline).

Phase B (daemon thread, ~1.5-2 s, runs in parallel with Phase A):
    Import every tool module and register tools on the shared ``mcp`` object.
    Set ``_tools_ready`` when done.

When the client sends ``tools/list`` (always after ``initialize``), the
patched handler awaits ``_tools_ready`` before returning, so the response
is deferred only if the background thread is still running.  In practice
Phase B finishes within ~200 ms of ``initialize`` being sent, so the client
never waits long.
"""

from __future__ import annotations

import threading
from typing import Any


def main() -> None:
    """Validate startup dependencies and launch the MCP server."""

    # ── Phase A: lightweight setup ─────────────────────────────────────────
    from rancher_mcp.config import validate_startup_settings
    from rancher_mcp.logging import configure_logging
    from rancher_mcp.services.catalog import get_capability_catalog

    settings = validate_startup_settings()
    configure_logging(settings.log_level)
    get_capability_catalog(settings.catalog_path)

    # FastMCP import is the heavy bit (~1.5 s); must happen before mcp.run().
    from anyio import to_thread
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        name=settings.server_name,
        instructions=settings.server_instructions,
    )

    # ── Phase B: background tool loading ───────────────────────────────────
    _tools_ready = threading.Event()

    def _load_tools() -> None:
        from rancher_mcp.server import register_all_tools

        register_all_tools(mcp)
        _tools_ready.set()

    threading.Thread(target=_load_tools, daemon=True, name="tool-loader").start()

    # ── Patch list_tools to wait for Phase B ───────────────────────────────
    # The low-level server stores the handler in request_handlers[ListToolsRequest].
    # Calling mcp._mcp_server.list_tools()(fn) overwrites it with our wrapper.
    _original_list_tools = mcp.list_tools

    async def _lazy_list_tools() -> list[Any]:
        """Block (async-friendly) until all tools are registered, then list."""
        await to_thread.run_sync(
            lambda: _tools_ready.wait(timeout=30),
            abandon_on_cancel=True,
        )
        return await _original_list_tools()  # type: ignore[return-value]

    mcp._mcp_server.list_tools()(_lazy_list_tools)  # type: ignore[attr-defined]

    mcp.run()


if __name__ == "__main__":
    main()
