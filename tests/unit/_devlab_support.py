"""Shared setup for the split devlab test modules.

Extracted from ``test_devlab.py`` when it was split by concern (kind, process,
rancher, imported, status) to stay under the architecture line limit. The
``_completed`` subprocess factory and the ``STATIC_REPO_ROOT`` constant are
consumed by several devlab test modules.
"""

import subprocess
from pathlib import Path

STATIC_REPO_ROOT = Path("/repo")


def _completed(
    args: list[str] | None = None,
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    """Build a completed process for subprocess mocks."""

    return subprocess.CompletedProcess(args or ["cmd"], returncode, stdout, stderr)
