"""Codegen entry point.

Reads every YAML descriptor under `catalog/curated_tools/`, validates,
plans, renders, formats, and writes generated files into
`src/rancher_mcp/tools/<pack>/`.

Usage:
    uv run python -m scripts.codegen.main
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.codegen.descriptor import (
    load_all_descriptors,
    load_all_pack_descriptors,
)
from scripts.codegen.emitter import emit_pack, make_environment
from scripts.codegen.formatter import format_files
from scripts.codegen.plan import build_pack_contexts

REPO_ROOT = Path(__file__).resolve().parents[2]
DESCRIPTORS_DIR = REPO_ROOT / "catalog" / "curated_tools"
SRC_ROOT = REPO_ROOT / "src"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate curated Rancher MCP tool modules from YAML descriptors."
    )
    parser.add_argument(
        "--pack",
        default=None,
        help="Limit codegen to one pack id (e.g. pods_services). Default: all packs.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print every emitted file path.",
    )
    args = parser.parse_args()

    descriptors = load_all_descriptors(DESCRIPTORS_DIR)
    packs = load_all_pack_descriptors(DESCRIPTORS_DIR)
    if not descriptors:
        print(f"No descriptors found in {DESCRIPTORS_DIR}", file=sys.stderr)
        return 0

    pack_contexts = build_pack_contexts(packs, descriptors)
    if args.pack is not None:
        pack_contexts = [ctx for ctx in pack_contexts if ctx.pack.id == args.pack]
        if not pack_contexts:
            print(f"No pack matching --pack={args.pack!r}", file=sys.stderr)
            return 1

    env = make_environment()
    written: list[Path] = []
    for pack_ctx in pack_contexts:
        written.extend(emit_pack(env, pack_ctx, SRC_ROOT))

    format_files(written)

    if args.verbose:
        for path in written:
            print(path.relative_to(REPO_ROOT))
    print(f"codegen wrote {len(written)} file(s) across {len(pack_contexts)} pack(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
