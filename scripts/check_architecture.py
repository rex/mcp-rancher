"""CLI wrapper for repo-local architecture checks."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from devtools.architecture_check import (  # noqa: E402
    check_architecture,
    load_vibe_policy,
    render_report,
)


def main() -> int:
    """Run the architecture check using repo policy."""

    policy = load_vibe_policy(REPO_ROOT)
    report = check_architecture(REPO_ROOT, policy)
    print(render_report(report))
    return 1 if report.has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
