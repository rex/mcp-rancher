"""Snapshot test for the curated-tool codegen.

Runs the generator into a temporary directory and compares its output
to the working tree. If a descriptor changed without `make codegen`,
this test fails (and `make check-codegen` would too).

Also exercises the descriptor schema validator on every committed
descriptor so a malformed YAML cannot land in the repo.
"""

from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

import pytest

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


def test_every_descriptor_validates() -> None:
    """Every committed descriptor parses against the Pydantic schema."""

    descriptors = load_all_descriptors(DESCRIPTORS_DIR)
    packs = load_all_pack_descriptors(DESCRIPTORS_DIR)
    assert descriptors, "expected at least one descriptor under catalog/curated_tools/"
    assert packs, "expected at least one pack metadata file under _packs/"
    # Every descriptor's pack must have a corresponding _packs/<id>.yml.
    referenced_packs = {d.pack for d in descriptors}
    missing = referenced_packs - set(packs.keys())
    assert not missing, f"descriptors reference packs without metadata: {missing}"


def test_codegen_output_matches_working_tree(tmp_path: Path) -> None:
    """Regenerating into a tmp dir must yield the same files as the working tree.

    Mirrors `make check-codegen` at the test layer so a CI run also enforces
    the contract. If this fails, run `make codegen` and commit the diff.
    """

    descriptors = load_all_descriptors(DESCRIPTORS_DIR)
    packs = load_all_pack_descriptors(DESCRIPTORS_DIR)
    pack_contexts = build_pack_contexts(packs, descriptors)

    # Mirror the source tree into tmp so emit_pack writes to the right
    # relative location, then regenerate from descriptors.
    fake_src = tmp_path / "src"
    shutil.copytree(SRC_ROOT, fake_src, dirs_exist_ok=False)

    env = make_environment()
    written: list[Path] = []
    for ctx in pack_contexts:
        written.extend(emit_pack(env, ctx, fake_src))
    format_files(written)

    # Diff every generated file against the working tree.
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
        joined = "\n  ".join(mismatches)
        pytest.fail(
            f"codegen output drifted from the working tree:\n  {joined}\n\n"
            "Run `make codegen` and commit the regenerated files."
        )
