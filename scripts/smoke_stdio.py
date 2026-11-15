#!/usr/bin/env python3
"""smoke_stdio.py — prove an installed rancher-mcp actually serves.

    python3 scripts/smoke_stdio.py --expect-version 1.2.3 -- uvx --from dist/x.whl rancher-mcp

Runs the given command the way an MCP client does and speaks to it over stdio,
once on each protocol era: the legacy ``initialize`` handshake and the
``2026-07-28`` ``server/discover`` probe. Each time it requires an answer that
names this server and the expected version, a full tool list, and a clean exit
when stdin closes.

Two things make it worth having over "does the process start":

* **It runs from an empty directory**, never the checkout. The release
  pipeline's smoke used to run from the repository root — where a
  repo-relative data file happened to exist — and passed for months while the
  published package crashed on startup for everyone who installed it.
* **It waits for the tools.** The server answers its first message before any
  tool module has loaded, and closing stdin straight away lets the process
  exit 0 before the loader has finished or failed. Asking for the tool list is
  the only way to learn that registration worked.

Standard library only, so it needs nothing installed and cannot import the
checkout by accident. No Rancher is contacted: listing tools is offline.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from typing import IO, Any

MODERN = "2026-07-28"
LEGACY = "2025-11-25"
MIN_TOOLS = 100
REPLY_DEADLINE_SECONDS = 60.0
_META = {
    "io.modelcontextprotocol/protocolVersion": MODERN,
    "io.modelcontextprotocol/clientInfo": {"name": "smoke-stdio", "version": "0"},
    "io.modelcontextprotocol/clientCapabilities": {},
}


class Failure(Exception):
    """One reason the server is not fit to publish."""


class Server:
    """A server process and the replies it has sent so far."""

    def __init__(self, command: list[str], cwd: str, env: dict[str, str]) -> None:
        self.process = subprocess.Popen(  # noqa: S603 (the command under test, from our own argv)
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        stdin, stdout, stderr = self.process.stdin, self.process.stdout, self.process.stderr
        if stdin is None or stdout is None or stderr is None:
            raise Failure("could not open the server's standard streams")
        self._stdin: IO[str] = stdin
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._stderr: list[str] = []
        # Reader threads rather than select(): select() on a buffered text
        # stream misses lines that arrived in the same chunk as the last one.
        threading.Thread(target=self._pump_stdout, args=(stdout,), daemon=True).start()
        threading.Thread(target=self._pump_stderr, args=(stderr,), daemon=True).start()

    def _pump_stdout(self, stream: IO[str]) -> None:
        for line in stream:
            self._lines.put(line)
        self._lines.put(None)

    def _pump_stderr(self, stream: IO[str]) -> None:
        for line in stream:
            self._stderr.append(line.rstrip())

    def send(self, method: str, params: dict[str, Any], request_id: int | None = None) -> None:
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params}
        if request_id is not None:
            message["id"] = request_id
        self._stdin.write(json.dumps(message) + "\n")
        self._stdin.flush()

    def reply_to(self, request_id: int) -> dict[str, Any]:
        """The result of request *request_id*, skipping anything else on the wire."""

        deadline = time.monotonic() + REPLY_DEADLINE_SECONDS
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Failure(f"no reply to request {request_id} in {REPLY_DEADLINE_SECONDS:g}s")
            try:
                line = self._lines.get(timeout=remaining)
            except queue.Empty:
                continue
            if line is None:
                raise Failure(f"the server exited before answering request {request_id}")
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                raise Failure(f"stdout carried something that is not JSON-RPC: {line!r}") from exc
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise Failure(f"request {request_id} failed: {json.dumps(message['error'])}")
            result: dict[str, Any] = message["result"]
            return result

    def close(self) -> int:
        self._stdin.close()
        try:
            return self.process.wait(timeout=30)
        except subprocess.TimeoutExpired as exc:
            self.process.kill()
            raise Failure("the server did not exit within 30s of stdin closing") from exc

    def stderr_tail(self) -> str:
        return "\n".join(f"    {line}" for line in self._stderr[-12:])


def check(era: str, command: list[str], env: dict[str, str], expect_version: str) -> str:
    """Run one handshake on one era. Returns a one-line account of it."""

    modern = era == "modern"
    meta = {"_meta": _META} if modern else {}
    with tempfile.TemporaryDirectory(prefix="rancher-mcp-smoke-") as elsewhere:
        server = Server(command, elsewhere, env)
        started = time.monotonic()
        try:
            if modern:
                server.send("server/discover", dict(meta), 1)
                hello = server.reply_to(1)
                spoken = hello.get("supportedVersions", [])
                if MODERN not in spoken:
                    raise Failure(f"server/discover does not offer {MODERN}: {spoken}")
            else:
                client = {"name": "smoke-stdio", "version": "0"}
                server.send(
                    "initialize",
                    {"protocolVersion": LEGACY, "capabilities": {}, "clientInfo": client},
                    1,
                )
                hello = server.reply_to(1)
                if hello.get("protocolVersion") != LEGACY:
                    raise Failure(f"initialize negotiated {hello.get('protocolVersion')!r}")
                server.send("notifications/initialized", {})
            first_answer = time.monotonic() - started

            # The legacy handshake names the server in its result; the modern
            # protocol has no handshake, so every result carries it in `_meta`.
            identity = hello.get("serverInfo") or hello.get("_meta", {}).get(
                "io.modelcontextprotocol/serverInfo", {}
            )
            if identity.get("version") != expect_version:
                raise Failure(
                    f"the server reports version {identity.get('version')!r}, "
                    f"expected {expect_version!r}"
                )

            server.send("tools/list", dict(meta), 2)
            tools = server.reply_to(2).get("tools", [])
            if len(tools) < MIN_TOOLS:
                raise Failure(f"tools/list returned {len(tools)} tools, expected {MIN_TOOLS}+")
            server.send("prompts/list", dict(meta), 3)
            prompts = server.reply_to(3).get("prompts", [])

            code = server.close()
            if code != 0:
                raise Failure(f"the server exited {code} when stdin closed")
        except Failure as failure:
            server.process.kill()
            raise Failure(
                f"{failure}\n  server stderr (last lines):\n{server.stderr_tail()}"
            ) from None
        return (
            f"{identity.get('name')} {identity.get('version')}: first answer in "
            f"{first_answer:.2f}s, {len(tools)} tools, {len(prompts)} prompts, clean exit"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Prove an installed rancher-mcp serves.")
    parser.add_argument("--expect-version", required=True)
    parser.add_argument("command", nargs="+", help="the server command, after `--`")
    args = parser.parse_args()

    # Only what a client would pass: no inherited RANCHER_* and no checkout on
    # PYTHONPATH. The credentials are placeholders — nothing here contacts Rancher.
    env = {
        key: os.environ[key]
        for key in ("PATH", "HOME", "TMPDIR", "LANG", "UV_CACHE_DIR", "XDG_CACHE_HOME")
        if key in os.environ
    }
    env["RANCHER_URL"] = "https://rancher.invalid"
    env["RANCHER_TOKEN"] = "token-smoke:placeholder"  # noqa: S105 - placeholder, not a credential  # pragma: allowlist secret

    failed = False
    for era in ("legacy", "modern"):
        try:
            print(f"✓ [{era}] {check(era, args.command, env, args.expect_version)}")
        except Failure as failure:
            failed = True
            print(f"✗ [{era}] {failure}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
