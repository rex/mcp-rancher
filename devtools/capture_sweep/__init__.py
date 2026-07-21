"""Exhaustive read-only MCP tool capture sweep against the local dev lab.

``make capture-sweep`` (``python -m devtools.capture_sweep``) drives every
satisfiable READ-ONLY tool through its real code path against the CURRENT
local Rancher lab, writes one JSON file per call to ``./capture/``, and
reports response sizes plus a residual-plumbing/long-string scan.

Package layout:

- ``constants`` — tunable bounds + shared parameter-name sets.
- ``naming`` — pure tool-name family/singularization helpers.
- ``pool`` — the discovered-resource ``Pool`` + the harvest step.
- ``combos`` — arg-combination planning from a tool's required params.
- ``scan`` — the plumbing/long-string response scanner.
- ``models`` — ``ToolPlan`` / ``SweepOutcome`` data structures.
- ``enumerator`` — tool registry introspection -> capture plan.
- ``login`` — lab login + lab-only ``AppSettings`` construction.
- ``crawler`` — the fixpoint wave-crawl orchestration.
- ``report`` — the human-readable summary report.
- ``cli`` — the ``python -m`` entrypoint.

Everything except ``crawler``/``login``/``cli`` (and ``enumerator``'s
registry-walking, which needs a live FastMCP instance) is pure logic with
no lab or network dependency — see ``tests/unit/test_capture_sweep_*.py``.
"""

from __future__ import annotations

from .cli import REPO_ROOT, main
from .combos import CallArgs, plan_calls, signature_key
from .constants import CALL_CAP, GLOBAL_ID_PARAMS, INJECTED_PARAMS
from .crawler import call_tool, run_sweep
from .enumerator import build_capture_plan, load_read_only_tool_names, resolve_impl_fn
from .login import SWEEP_INSTANCE_NAME, LabUnreachableError, build_sweep_settings, login_to_lab
from .models import SweepOutcome, ToolPlan
from .naming import get_family, list_family, singularize
from .pool import Pool, harvest
from .report import build_report, write_report
from .scan import PLUMBING, ScanFlags, scan_dump

__all__ = [
    "CALL_CAP",
    "GLOBAL_ID_PARAMS",
    "INJECTED_PARAMS",
    "PLUMBING",
    "REPO_ROOT",
    "SWEEP_INSTANCE_NAME",
    "CallArgs",
    "LabUnreachableError",
    "Pool",
    "ScanFlags",
    "SweepOutcome",
    "ToolPlan",
    "build_capture_plan",
    "build_report",
    "build_sweep_settings",
    "call_tool",
    "get_family",
    "harvest",
    "list_family",
    "load_read_only_tool_names",
    "login_to_lab",
    "main",
    "plan_calls",
    "resolve_impl_fn",
    "run_sweep",
    "scan_dump",
    "signature_key",
    "singularize",
    "write_report",
]
