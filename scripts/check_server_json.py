#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""check_server_json.py — validate server.json against MCP Registry constraints.

Catches, locally, the traps that otherwise only surface as a failed
tag-triggered registry publish (a red release run after PyPI already shipped):

  - `description` must be <= 100 characters (registry hard limit — it returns a
    422 "expected length <= 100" otherwise; this bit v1.12.2).
  - server.json must be valid JSON.

Wired into `make validate` and pre-commit. Exit 1 on any violation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SERVER_JSON = Path(__file__).resolve().parent.parent / "server.json"
_MAX_DESCRIPTION = 100


def main() -> int:
    try:
        data = json.loads(SERVER_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"✗ server.json is not readable / valid JSON: {exc}", file=sys.stderr)
        return 1

    description = str(data.get("description", ""))
    if len(description) > _MAX_DESCRIPTION:
        print(
            f"✗ server.json description is {len(description)} chars — the MCP Registry "
            f"limit is {_MAX_DESCRIPTION}, so the tag-triggered publish will 422. "
            "Shorten it before tagging.",
            file=sys.stderr,
        )
        return 1

    print(f"✓ server.json OK (description {len(description)}/{_MAX_DESCRIPTION} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
