"""CLI entrypoint.

Startup strategy
----------------
``from mcp.server.fastmcp import FastMCP`` alone takes ~1.5-2 s on this
machine.  Loading all 100+ tool modules on top pushes total startup past the
~3 s threshold at which Claude Code gives up waiting for the MCP
``initialize`` response.

To fix this we split startup into three phases:

Phase 0 (pure stdlib, <10 ms):
    Read the ``initialize`` request from stdin and send the response
    immediately using only ``json`` / ``sys`` — before importing *anything*
    else.  Claude Code gets its handshake reply in milliseconds.
    A background OS pipe is set up so subsequent stdin messages are buffered
    until the real FastMCP event loop is ready.

Phase A (main thread, ~1.7 s total, overlaps Phase 0):
    Import FastMCP, create a bare server instance.  Because we already
    handled ``initialize``, FastMCP is configured with ``stateless=True``
    so it won't wait for a second initialize handshake.  Kick off Phase B.
    Override ``list_tools`` to block until Phase B finishes.

Phase B (daemon thread, ~1.5 s, runs in parallel with Phase A):
    Import every tool module and register tools on the shared ``mcp`` object.
    Set ``_tools_ready`` when done.

When the client sends ``tools/list`` (always after ``initialize``), the
patched handler awaits ``_tools_ready`` before returning, so the response
is deferred only if the background thread is still running.
"""

from __future__ import annotations

import contextlib
import os
import sys
import threading
from typing import Any


def main() -> None:  # noqa: PLR0915
    """Validate startup dependencies and launch the MCP server."""
    import json

    # ── Phase 0: early initialize response (pure stdlib) ──────────────────
    # Read the first line from stdin.  The MCP client always sends
    # ``initialize`` as the very first message, so we can respond immediately
    # without any heavy imports.
    _real_stdin_buf = sys.stdin.buffer
    _init_line = _real_stdin_buf.readline()

    _init_msg: Any = None
    with contextlib.suppress(json.JSONDecodeError, ValueError):
        _init_msg = json.loads(_init_line)

    _early_init_sent = False
    if _init_msg and _init_msg.get("method") == "initialize":
        _params: Any = _init_msg.get("params") or {}
        _protocol_version: str = _params.get("protocolVersion") or "2024-11-05"
        _response = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": _init_msg["id"],
                "result": {
                    "protocolVersion": _protocol_version,
                    "capabilities": {
                        "experimental": {},
                        "prompts": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                        "tools": {"listChanged": False},
                    },
                    "serverInfo": {"name": "rancher-mcp", "version": "1.0.0"},
                    "instructions": (
                        "Capability-aware Rancher MCP server for Rancher 2.6.5"
                    ),
                },
            }
        )
        sys.stdout.buffer.write((_response + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
        _early_init_sent = True

    # Pipe remaining stdin to FastMCP (exclude the initialize message we
    # already consumed).  FastMCP will read from the pipe read end.
    _pipe_r, _pipe_w = os.pipe()

    def _pipe_stdin() -> None:
        """Copy real stdin → pipe write end."""
        with os.fdopen(_pipe_w, "wb", 0) as _w:
            if not _early_init_sent and _init_line:
                # initialize wasn't sent early; replay the first line so
                # FastMCP handles it normally.
                _w.write(_init_line if _init_line.endswith(b"\n") else _init_line + b"\n")
            while True:
                _chunk = _real_stdin_buf.read(65536)
                if not _chunk:
                    break
                _w.write(_chunk)

    threading.Thread(target=_pipe_stdin, daemon=True, name="stdin-pipe").start()

    # Replace sys.stdin so stdio_server() picks up the pipe.
    # stdio_server wraps sys.stdin.buffer; os.fdopen gives us the BinaryIO.
    import io as _io

    _pipe_r_file = os.fdopen(_pipe_r, "rb", 0)
    sys.stdin = _io.TextIOWrapper(_pipe_r_file, encoding="utf-8")  # type: ignore[assignment]

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
    from mcp.server.stdio import stdio_server

    mcp = FastMCP(
        name="rancher-mcp",
        instructions="Capability-aware Rancher MCP server for Rancher 2.6.5",
    )

    # If we sent the early initialize response, patch run_stdio_async to use
    # stateless=True so FastMCP doesn't wait for (or re-send) an initialize
    # handshake it will never see.
    if _early_init_sent:

        async def _stateless_run_stdio_async() -> None:
            async with stdio_server() as (read_stream, write_stream):
                await mcp._mcp_server.run(  # type: ignore[attr-defined]
                    read_stream,
                    write_stream,
                    mcp._mcp_server.create_initialization_options(),  # type: ignore[attr-defined]
                    stateless=True,
                )

        mcp.run_stdio_async = _stateless_run_stdio_async  # type: ignore[method-assign]

    # ── Phase B: background tool loading ───────────────────────────────────
    _tools_ready = threading.Event()

    def _load_tools() -> None:
        from rancher_mcp.server import register_all_tools

        register_all_tools(mcp)
        _tools_ready.set()

    threading.Thread(target=_load_tools, daemon=True, name="tool-loader").start()

    # ── Patch list_tools to wait for Phase B ───────────────────────────────
    _original_list_tools = mcp.list_tools

    async def _lazy_list_tools() -> list[Any]:
        """Block (async-friendly) until all tools are registered, then list."""
        await to_thread.run_sync(
            lambda: _tools_ready.wait(timeout=30),
            cancellable=True,
        )
        return await _original_list_tools()  # type: ignore[return-value]

    mcp._mcp_server.list_tools()(_lazy_list_tools)  # type: ignore[attr-defined]

    mcp.run()


if __name__ == "__main__":
    main()
