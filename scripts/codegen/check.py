"""Drift check: regenerate into a temp dir and diff against the working tree.

Used by `make check-codegen` to verify the committed generated files match
their descriptors. Independent of `git` state so it works pre-commit and in
CI alike.
"""

from __future__ import annotations

import filecmp
import shutil
import sys
import tempfile
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
    descriptors = load_all_descriptors(DESCRIPTORS_DIR)
    packs = load_all_pack_descriptors(DESCRIPTORS_DIR)
    pack_contexts = build_pack_contexts(packs, descriptors)

    with tempfile.TemporaryDirectory() as tmp:
        fake_src = Path(tmp) / "src"
        shutil.copytree(SRC_ROOT, fake_src)
        env = make_environment()
        written: list[Path] = []
        for ctx in pack_contexts:
            written.extend(emit_pack(env, ctx, fake_src))
        format_files(written)

        mismatches: list[str] = []
        for written_path in written:
            relative = written_path.relative_to(fake_src)
            repo_path = SRC_ROOT / relative
            if not repo_path.exists():
                mismatches.append(f"missing in working tree: {relative}")
                continue
            if not filecmp.cmp(written_path, repo_path, shallow=False):
                mismatches.append(f"differs from working tree: {relative}")

    if mismatches:
        print("\033[31mcodegen output drifted from working tree:\033[0m", file=sys.stderr)
        for mismatch in mismatches:
            print(f"  {mismatch}", file=sys.stderr)
        print(
            "\nRun `make codegen` and commit the regenerated files.",
            file=sys.stderr,
        )
        return 1
    print(f"codegen check ok: {len(written)} file(s) match their descriptors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
