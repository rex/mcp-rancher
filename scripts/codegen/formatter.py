"""Run ruff format on emitted files."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def format_files(paths: list[Path]) -> None:
    """Run `ruff format` then `ruff check --fix` on the given paths."""

    if not paths:
        return
    ruff = shutil.which("ruff") or "ruff"
    subprocess.run(  # noqa: S603 (ruff is project-pinned)
        [ruff, "format", "--quiet", *(str(p) for p in paths)],
        check=True,
    )
    subprocess.run(  # noqa: S603
        [ruff, "check", "--fix", "--quiet", *(str(p) for p in paths)],
        check=False,  # tolerate non-fixable lints; codegen output should be clean
    )
