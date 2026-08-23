"""A fatal startup failure must be visible at ANY log level.

Two independent bugs made this silent, and the second hid behind the first:

1. Tool registration runs on a daemon thread. An unhandled exception there does
   not crash the process — the thread just dies, `_tools_ready` is never set,
   and the server sat accepting a `tools/list` it could never answer until a
   30-second timeout expired.
2. Once that was fixed, the diagnostic still went through a level-filtered
   `.error()` call. Under `LOG_LEVEL=CRITICAL` the process exited 1 with a
   **completely empty stderr** — an operator got a bare exit code and nothing
   else, which is the exact opposite of failing loudly.

So the report is now written straight to stderr before the structured log:
logging may itself be the thing that is misconfigured, which makes the
structured call the least trustworthy way to report a misconfiguration.

This spawns a real subprocess because that is the only place the behavior
exists — the interaction is between a daemon thread, the logging config, and
process exit. A unit-level fake would assert nothing about any of them.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "startup-test", "version": "1"},
    },
}


def _start_with_bad_profile(log_level: str) -> tuple[int | None, str]:
    env = dict(os.environ)
    env.update(
        {
            "RANCHER_TOOLSETS": "definitely-not-a-real-profile",
            "RANCHER_URL": "https://unused.invalid",
            "RANCHER_TOKEN": "unused",  # pragma: allowlist secret
            "LOG_LEVEL": log_level,
        }
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "rancher_mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(_INITIALIZE) + "\n")
    proc.stdin.flush()
    try:
        returncode = proc.wait(timeout=30)
    except subprocess.TimeoutExpired:  # pragma: no cover - failure path
        proc.kill()
        pytest.fail(
            "server did not exit on a fatal registration error — it is hanging, "
            "serving a tool list it can never produce"
        )
    assert proc.stderr is not None
    return returncode, proc.stderr.read()


@pytest.mark.parametrize("log_level", ["INFO", "CRITICAL"])
def test_unknown_toolset_profile_exits_loudly_at_any_log_level(log_level: str) -> None:
    returncode, stderr = _start_with_bad_profile(log_level)

    assert returncode == 1, f"expected a hard exit, got {returncode!r}"
    assert stderr.strip(), (
        f"process died with an EMPTY stderr under LOG_LEVEL={log_level}. An operator "
        "gets an exit code and no reason — this is the silent-death regression."
    )
    assert "FATAL:" in stderr
    # The message must be actionable: name the bad value AND the valid set.
    assert "definitely-not-a-real-profile" in stderr
    assert "core" in stderr, "the error should list valid profiles so the typo is fixable"
