"""CLI entrypoint: ``uv run python -m devtools.capture_sweep``.

Drives the full read-only capture sweep against the CURRENT local dev lab
(``make lab-current-up``), then prints and saves the summary report. No
flags: the sweep always targets the CURRENT profile and always writes to
``<repo_root>/capture/``.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from devtools.capture_sweep.crawler import run_sweep
from devtools.capture_sweep.login import LabUnreachableError
from devtools.capture_sweep.report import build_report, write_report

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    """Run the capture sweep; print + save the report. Returns a process exit code."""

    capture_dir = REPO_ROOT / "capture"
    try:
        outcome = asyncio.run(run_sweep(REPO_ROOT, capture_dir))
    except LabUnreachableError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not outcome.records:
        print("No calls were made (preflight failed) — see output above.", file=sys.stderr)
        return 1

    report_text = build_report(outcome.records, outcome.read_only_tools, outcome.pool)
    print(report_text)
    written = write_report(report_text, capture_dir)
    print(f"\nreport -> {written}")
    print("manifest -> capture_manifest.json")
    return 0
