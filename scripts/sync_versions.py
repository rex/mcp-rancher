#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""sync_versions.py — propagate VERSION into every version-bearing file.

The vendored skeleton ``bump_version.py`` writes only ``VERSION`` +
``CHANGELOG.md``. This project-owned companion keeps the *other* version
fields in lockstep with ``VERSION`` on every commit:

  - ``pyproject.toml``      → ``[project].version``
  - ``server.json``         → top-level ``version`` **and** every ``packages[*].version``
  - ``uv.lock``             → the editable ``rancher-mcp`` package entry

Why continuous sync (not just at release): the tag-triggered publish is the
ONLY thing that ships a package, so rewriting these files on every commit is
risk-free — and it means a server built straight from source self-reports the
correct version, and the release guard (tag == VERSION == pyproject ==
server.json) can never trip. Packaged releases stay gated separately by the tag.

Modes:
  (default)  rewrite the files to match VERSION.
  --check    exit 1 if any file drifts from VERSION (the pre-commit gate).

Wired into pre-commit (``--check``), ``make sync-versions`` (write), and
``make validate`` (``--check``). A version-only edit to ``uv.lock`` is exactly
what ``uv lock`` produces for the local editable package (no dependency-graph
change), so the direct edit is canonical; run ``uv lock`` only when deps move.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
PYPROJECT = ROOT / "pyproject.toml"
SERVER_JSON = ROOT / "server.json"
UV_LOCK = ROOT / "uv.lock"
PACKAGE_NAME = "rancher-mcp"


def read_version() -> str:
    """The single source of truth."""

    return VERSION_FILE.read_text(encoding="utf-8").strip()


def sync_pyproject(version: str, *, write: bool) -> str | None:
    """Sync ``[project].version`` (the only bare ``^version =`` line)."""

    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'(?m)^version = "([^"]*)"', text)
    current = match.group(1) if match else None
    if current == version:
        return None
    if write and match is not None:
        text = re.sub(r'(?m)^(version = ")[^"]*(")', rf"\g<1>{version}\g<2>", text, count=1)
        PYPROJECT.write_text(text, encoding="utf-8")
    return f"pyproject.toml [project].version: {current} -> {version}"


def sync_server_json(version: str, *, write: bool) -> list[str]:
    """Sync the top-level ``version`` and every ``packages[*].version``."""

    data = json.loads(SERVER_JSON.read_text(encoding="utf-8"))
    drifts: list[str] = []
    if data.get("version") != version:
        drifts.append(f"server.json .version: {data.get('version')} -> {version}")
        data["version"] = version
    for index, package in enumerate(data.get("packages", [])):
        if package.get("version") != version:
            drifts.append(
                f"server.json .packages[{index}].version: {package.get('version')} -> {version}"
            )
            package["version"] = version
    if drifts and write:
        SERVER_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return drifts


def sync_uv_lock(version: str, *, write: bool) -> str | None:
    """Sync the editable ``rancher-mcp`` package entry's ``version``."""

    text = UV_LOCK.read_text(encoding="utf-8")
    pattern = re.compile(rf'(?m)^(name = "{re.escape(PACKAGE_NAME)}"\nversion = ")([^"]*)(")')
    match = pattern.search(text)
    if match is None:
        return f'uv.lock: package entry name = "{PACKAGE_NAME}" not found'
    current = match.group(2)
    if current == version:
        return None
    if write:
        text = pattern.sub(rf"\g<1>{version}\g<3>", text, count=1)
        UV_LOCK.write_text(text, encoding="utf-8")
    return f"uv.lock [{PACKAGE_NAME}].version: {current} -> {version}"


def collect_drifts(version: str, *, write: bool) -> list[str]:
    """Apply (or, when ``write`` is False, only report) every sync."""

    drifts: list[str] = []
    pyproject = sync_pyproject(version, write=write)
    if pyproject:
        drifts.append(pyproject)
    drifts.extend(sync_server_json(version, write=write))
    uv_lock = sync_uv_lock(version, write=write)
    if uv_lock:
        drifts.append(uv_lock)
    return drifts


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync version-bearing files to VERSION.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 on drift instead of rewriting (the pre-commit gate).",
    )
    args = parser.parse_args()
    version = read_version()
    drifts = collect_drifts(version, write=not args.check)
    if not drifts:
        return 0
    if args.check:
        print(f"Version files drifted from VERSION={version}:", file=sys.stderr)
        for drift in drifts:
            print(f"  - {drift}", file=sys.stderr)
        print(
            "Fix: `make sync-versions` (or python scripts/sync_versions.py), then re-stage.",
            file=sys.stderr,
        )
        return 1
    print(f"Synced version files to {version}:")
    for drift in drifts:
        print(f"  - {drift}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
