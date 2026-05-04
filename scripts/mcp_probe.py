"""Manually drive the rancher-mcp stdio server and report health.

Reads the configured launch command + environment from ``~/.claude.json``
under ``mcpServers["rancher-mcp"]`` (so what we test is exactly what Claude
launches), spawns the server as a subprocess, and walks it through:

  1. ``initialize`` — measures handshake latency (Phase 0 fast-path)
  2. ``notifications/initialized`` — formal post-handshake notification
  3. ``tools/list`` — measures Phase B readiness + reports tool count

Use whenever Claude reports the server "failed to connect" or shows the
server connected but with no tools loaded — this harness isolates whether
the problem is on the server side or in Claude's MCP plumbing.

Usage:
    uv run python scripts/mcp_probe.py
    uv run python scripts/mcp_probe.py --instance lab
    uv run python scripts/mcp_probe.py --tools-warmup-seconds 12

Exit code is 0 on a successful initialize + tools/list with at least one
tool registered, 1 otherwise.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, cast


def _load_launch_spec(server_name: str) -> tuple[list[str], dict[str, str]]:
    """Read launch command + env from the user-level Claude config."""
    cfg_path = Path(os.path.expanduser("~/.claude.json"))
    cfg = json.loads(cfg_path.read_text())
    entry = cfg["mcpServers"][server_name]
    cmd = [entry["command"], *entry["args"]]
    env = os.environ.copy()
    env.update(entry.get("env") or {})
    return cmd, env


def _start_reader(stream: Any, sink: list[str]) -> threading.Thread:
    def reader() -> None:
        for line in iter(stream.readline, b""):
            sink.append(line.decode("utf-8", "replace").rstrip())

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    return thread


def _await_id(
    responses: list[str], request_id: int, timeout: float
) -> tuple[dict[str, Any] | None, float]:
    """Wait until a JSON-RPC response with ``id == request_id`` arrives."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for line in responses:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("id") == request_id:
                return obj, deadline - time.time()
        time.sleep(0.05)
    return None, 0.0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manually drive the rancher-mcp stdio server and report health."
    )
    parser.add_argument(
        "--server-name",
        default="rancher-mcp",
        help="Name of the server entry under mcpServers in ~/.claude.json",
    )
    parser.add_argument(
        "--instance",
        default=None,
        help="Override RANCHER_DEFAULT_INSTANCE for this probe (prod, lab, ...)",
    )
    parser.add_argument(
        "--tools-warmup-seconds",
        type=float,
        default=8.0,
        help="Seconds to wait between initialized and tools/list",
    )
    parser.add_argument(
        "--initialize-timeout",
        type=float,
        default=5.0,
        help="Seconds to wait for the initialize response",
    )
    parser.add_argument(
        "--tools-list-timeout",
        type=float,
        default=20.0,
        help="Seconds to wait for the tools/list response",
    )
    args = parser.parse_args()

    cmd, env = _load_launch_spec(args.server_name)
    if args.instance:
        env["RANCHER_DEFAULT_INSTANCE"] = args.instance

    print(f"launching: {cmd[0]} {' '.join(cmd[1:])}")
    print(f"default instance: {env.get('RANCHER_DEFAULT_INSTANCE', '<unset>')}")

    # The launch command comes from the user's own ~/.claude.json — it is the
    # exact thing Claude itself executes, not user input from the network.
    proc = subprocess.Popen(  # noqa: S603 (launch spec read from local config)
        cmd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    if not (proc.stdin and proc.stdout and proc.stderr):  # pragma: no cover
        raise RuntimeError("subprocess pipes not opened")
    proc_stdin = proc.stdin

    responses: list[str] = []
    errors: list[str] = []
    _start_reader(proc.stdout, responses)
    _start_reader(proc.stderr, errors)

    def send(payload: dict[str, Any]) -> None:
        proc_stdin.write((json.dumps(payload) + "\n").encode())
        proc_stdin.flush()

    rc = 0

    try:
        # ── initialize ─────────────────────────────────────────────────────
        t_init = time.time()
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "mcp_probe", "version": "0.0"},
                },
            }
        )
        init_resp, _ = _await_id(responses, 1, args.initialize_timeout)
        init_ms = (time.time() - t_init) * 1000.0
        if init_resp is None:
            print(f"initialize: NO RESPONSE in {args.initialize_timeout}s")
            rc = 1
        else:
            result = cast(dict[str, Any], init_resp.get("result") or {})
            server_info = cast(dict[str, Any], result.get("serverInfo") or {})
            print(
                f"initialize: ok in {init_ms:.0f} ms "
                f"({server_info.get('name')!r} {server_info.get('version')!r})"
            )

        # ── initialized notification ───────────────────────────────────────
        send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

        # ── give Phase B time to register tools ────────────────────────────
        if args.tools_warmup_seconds > 0:
            print(f"warmup: sleeping {args.tools_warmup_seconds:.1f}s for tool registration")
            time.sleep(args.tools_warmup_seconds)

        # ── tools/list ─────────────────────────────────────────────────────
        t_list = time.time()
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        list_resp, _ = _await_id(responses, 2, args.tools_list_timeout)
        list_ms = (time.time() - t_list) * 1000.0
        if list_resp is None:
            print(f"tools/list: NO RESPONSE in {args.tools_list_timeout}s")
            rc = 1
        elif list_resp.get("error"):
            print(f"tools/list: error: {list_resp['error']}")
            rc = 1
        else:
            list_result = cast(dict[str, Any], list_resp.get("result") or {})
            tools = cast(list[dict[str, Any]], list_result.get("tools") or [])
            print(f"tools/list: ok in {list_ms:.0f} ms — {len(tools)} tools")
            for tool in tools[:10]:
                print(f"  - {tool.get('name')}")
            if len(tools) > 10:
                print(f"  ... and {len(tools) - 10} more")
            if not tools:
                rc = 1
    finally:
        with contextlib.suppress(BrokenPipeError):
            proc_stdin.close()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

    if errors:
        print(f"\nstderr: {len(errors)} lines, last 15:")
        for line in errors[-15:]:
            print(f"  {line}")

    return rc


if __name__ == "__main__":
    sys.exit(main())
