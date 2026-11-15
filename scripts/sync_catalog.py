#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""sync_catalog.py — keep the capability catalog that ships in the wheel current.

`catalog/capabilities.yaml` is the file people edit. But `catalog/` sits at the
repository root, outside the package, so it is not in the wheel — and the
server reads the catalog before it serves anything. For as long as the default
path pointed there, `uvx rancher-mcp` crashed on startup from every directory
that was not a checkout of this repository, which is every directory a user
runs it from.

So a copy lives inside the package (`src/rancher_mcp/catalog_data/`), the
server defaults to that copy, and this script is what keeps the two identical:

    make sync-catalog     rewrite the packaged copy from the source
    make check-catalog    fail if they differ (wired into `make validate`)

The packaged copy is generated. Edit `catalog/capabilities.yaml`, then sync.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "catalog" / "capabilities.yaml"
PACKAGED = ROOT / "src" / "rancher_mcp" / "catalog_data" / "capabilities.yaml"


def main(argv: list[str]) -> int:
    source = SOURCE.read_bytes()
    current = PACKAGED.read_bytes() if PACKAGED.exists() else None
    shown = PACKAGED.relative_to(ROOT)

    if "--check" in argv:
        if current == source:
            print(f"✓ {shown} matches catalog/capabilities.yaml")
            return 0
        state = "is missing" if current is None else "differs from catalog/capabilities.yaml"
        print(
            f"✗ {shown} {state}. It is the copy that ships in the wheel, so an "
            "installed server would run on a stale catalog. Run `make sync-catalog`.",
            file=sys.stderr,
        )
        return 1

    if current == source:
        print(f"✓ {shown} already current")
        return 0
    PACKAGED.parent.mkdir(parents=True, exist_ok=True)
    PACKAGED.write_bytes(source)
    print(f"✓ wrote {shown} from catalog/capabilities.yaml ({len(source)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
