"""CLI entrypoint.

Startup strategy
----------------
A client's first message has a deadline. Claude Code probes a stdio server
with ``server/discover`` the moment the process starts and waits about three
seconds for the answer (2.93 s measured); after that it sends a legacy
``initialize`` and the connection is served on the old protocol. Importing the
SDK takes ~0.7-1.4 s and importing every tool module costs more again — and
both happen while the client is itself starting and competing for the CPU. See
``docs/reference/claude-code-mcp-client.md`` §4.

So startup is split in two, running concurrently:

Phase A (main thread):
    Config, logging, the SDK import, and a bare server that already knows its
    name, version, capabilities and instructions — which is all
    ``server/discover`` or ``initialize`` need. Then ``mcp.run()``.

Phase B (daemon thread):
    Import every tool module and register tools, prompts and resources on the
    shared server; set the ready flag.

Every request that reads the registry waits for Phase B (see
``rancher_mcp.server.hold_requests_until``). In practice Phase B finishes
within a few hundred milliseconds of the first request, so nobody waits long.
"""

from __future__ import annotations

import threading


def main() -> None:
    """Validate startup dependencies and launch the MCP server."""

    # ── Phase A: lightweight setup ─────────────────────────────────────────
    from rancher_mcp.config import validate_startup_settings
    from rancher_mcp.logging import configure_logging
    from rancher_mcp.services.catalog import get_capability_catalog

    settings = validate_startup_settings()
    configure_logging(settings.log_level)
    get_capability_catalog(settings.catalog_path)

    # Importing `rancher_mcp.server` imports the SDK — the heavy bit of Phase A,
    # and it has to finish before `mcp.run()` can answer anything.
    from rancher_mcp.server import hold_requests_until, new_server

    mcp = new_server(settings.server_name, settings.server_instructions)

    # ── Hold registry-reading requests until Phase B finishes ──────────────
    # Installed BEFORE the loader thread exists, not after it starts: both
    # replace methods on the same server object, and two threads doing that at
    # once can lose one of the replacements. This way the hold always goes on
    # first and everything the loader installs stacks on top of it.
    _tools_ready = threading.Event()
    hold_requests_until(mcp, _tools_ready)

    # ── Phase B: background tool loading ───────────────────────────────────
    def _load_tools() -> None:
        from rancher_mcp.server import register_all_tools

        try:
            register_all_tools(mcp)
        except Exception as exc:
            # A daemon thread's unhandled exception does NOT crash the
            # process — Python just prints it via threading.excepthook and
            # the thread dies, leaving `_tools_ready` unset forever. Left
            # alone, that means every held request below blocks silently for
            # its full timeout before failing: a misconfiguration (e.g.
            # an unknown RANCHER_TOOLSETS profile) would "fail loudly" only
            # in the sense of a buried stderr traceback, not to the operator
            # watching the process start. Report it, then exit hard — a
            # server that cannot register its tools has nothing to serve.
            import sys
            import traceback

            # Written straight to stderr, ahead of the structured log, for two
            # reasons. It must survive any LOG_LEVEL — at CRITICAL an
            # `.error()` here is filtered and the process died with exit 1 and
            # a COMPLETELY EMPTY stderr, which is the opposite of failing
            # loudly. And logging may itself be what is misconfigured, in
            # which case the structured call is the least trustworthy way to
            # report that something is misconfigured.
            print(
                f"FATAL: rancher-mcp could not register its tools: {exc}",
                file=sys.stderr,
                flush=True,
            )
            traceback.print_exc(file=sys.stderr)

            import structlog

            structlog.get_logger("rancher_mcp.startup").critical(
                "tool_registration_failed", exc_info=True
            )
            import os

            # os._exit, not sys.exit: SystemExit raised on a non-main thread
            # only unwinds that thread and would leave the server running,
            # accepting requests it can never answer.
            os._exit(1)
        _tools_ready.set()

    threading.Thread(target=_load_tools, daemon=True, name="tool-loader").start()

    mcp.run()


if __name__ == "__main__":
    main()
