"""Fixpoint crawl: drive every satisfiable read-only tool against the lab.

Orchestrates the whole sweep: configures logging, logs into the lab,
registers every MCP tool, plans+executes calls wave over wave (each wave's
discoveries feed the next wave's arg combinations) until a fixpoint, and
writes one JSON file per call to the capture directory.
"""

# This module intentionally reaches into two private/internal symbols:
# ``rancher_mcp.tools.support.errors._error_envelope`` (so a captured error
# record matches the exact envelope shape a real MCP client would see for
# the same failure) and FastMCP's ``_tool_manager._tools`` registry (no
# public API lists "every registered tool + its raw callable" — see
# ``enumerator.resolve_impl_fn``). reportPrivateUsage is disabled for
# these intentional, documented reaches only.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from mcp.server.fastmcp import FastMCP

from devtools.capture_sweep.combos import plan_calls, signature_key
from devtools.capture_sweep.constants import CALL_CAP
from devtools.capture_sweep.enumerator import (
    build_capture_plan,
    load_read_only_tool_names,
    resolve_impl_fn,
)
from devtools.capture_sweep.login import SWEEP_INSTANCE_NAME, build_sweep_settings, login_to_lab
from devtools.capture_sweep.models import SweepOutcome, ToolPlan
from devtools.capture_sweep.pool import Pool, harvest
from devtools.capture_sweep.scan import scan_dump
from devtools.devlab.models import LabConfig
from devtools.devlab.profiles import LabProfile
from rancher_mcp.config import AppSettings
from rancher_mcp.logging import configure_logging
from rancher_mcp.server import register_all_tools
from rancher_mcp.tools.support.errors import _error_envelope

# Between-call pause: keeps a ~300-call wave from hammering the lab's
# single kind-backed control plane in a tight loop.
_INTER_CALL_DELAY_SECONDS = 0.01


async def call_tool(
    fn: Callable[..., Any], args: dict[str, str], settings: AppSettings
) -> tuple[bool, object, str | None]:
    """Invoke one tool's IMPL fn directly. Never raises: failures become data."""

    try:
        result = fn(**args, instance=SWEEP_INSTANCE_NAME, settings=settings)
        if inspect.isawaitable(result):
            result = await result
        return True, _as_json_shape(result), None
    except Exception as exc:
        # Intentionally broad: a sweep drives ~300 tools through arbitrary,
        # often-unsatisfiable id combinations. Any one call's failure is
        # expected, structured, and captured as data (never swallowed) —
        # never a reason to abort the rest of the run.
        envelope = _safe_error_envelope(exc)
        return False, envelope, envelope.get("error_code") or envelope.get("error")


def _as_json_shape(result: object) -> object:
    """Render a tool result (a Pydantic model or plain value) as JSON-shaped data."""

    model_dump = getattr(result, "model_dump", None)
    if callable(model_dump):
        return model_dump(by_alias=True)
    return result


def _safe_error_envelope(exc: Exception) -> dict[str, Any]:
    """Build the same structured error envelope a real MCP client would see."""

    try:
        envelope: dict[str, Any] = json.loads(_error_envelope(exc))
    except Exception:
        # Envelope-building itself must never abort the sweep — fall back
        # to a minimal, always-JSON-serializable shape.
        envelope = {"error": f"{type(exc).__name__}: {exc}"}
    return envelope


def _resolve_impl_fns(mcp: Any, plans: list[ToolPlan]) -> dict[str, Callable[..., Any]]:
    """Resolve every planned tool's real IMPL fn once, up front."""

    tools: dict[str, Any] = mcp._tool_manager._tools
    return {plan.tool: resolve_impl_fn(tools[plan.tool].fn, plan.tool) for plan in plans}


async def run_sweep(repo_root: Path, capture_dir: Path) -> SweepOutcome:
    """Run the full read-only capture sweep against the CURRENT dev lab.

    Raises ``LabUnreachableError`` if the lab cannot be reached; callers
    should catch it for a clean CLI error message.
    """

    # Load-bearing: without this, structlog's library default renders
    # exceptions with locals (would dump the settings/token repr on any
    # tool error) instead of the quiet, level-gated JSON renderer the
    # production server configures at startup.
    configure_logging("CRITICAL")

    capture_dir.mkdir(parents=True, exist_ok=True)
    for stale in capture_dir.glob("*.json"):
        stale.unlink()

    cfg = LabConfig.from_env(repo_root, LabProfile.CURRENT)
    token = login_to_lab(cfg)
    settings = build_sweep_settings(cfg, token, repo_root)

    mcp = FastMCP("rancher-mcp-capture-sweep")
    register_all_tools(mcp)
    read_only_tools = load_read_only_tool_names(repo_root)
    plan = build_capture_plan(mcp, read_only_tools)
    ro_plans = [p for p in plan if p.read_only]
    impl_fns = _resolve_impl_fns(mcp, ro_plans)

    pool = Pool()
    records: list[dict[str, Any]] = []
    executed: set[tuple[str, str]] = set()
    call_index = 0

    print(f"lab: {cfg.rancher_loopback_url}  read-only tools: {len(ro_plans)}")
    preflight_fn = impl_fns.get("rancher_clusters_list")
    if preflight_fn is not None:
        ok, dump, err = await call_tool(preflight_fn, {}, settings)
        if not ok:
            print(f"PREFLIGHT FAILED — clusters_list errored: {err} {json.dumps(dump)[:300]}")
            return SweepOutcome(records, read_only_tools, pool)
        harvest("rancher_clusters_list", None, dump, pool)
        print(f"clusters discovered: {pool.clusters}")

    wave = 0
    while True:
        wave += 1
        new_calls = 0
        for tool_plan in ro_plans:
            fn = impl_fns[tool_plan.tool]
            for args in plan_calls(tool_plan, pool):
                key = (tool_plan.tool, signature_key(args))
                if key in executed:
                    continue
                executed.add(key)
                if call_index >= CALL_CAP:
                    break
                call_index += 1
                new_calls += 1
                ok, dump, err = await call_tool(fn, args, settings)
                if ok:
                    harvest(tool_plan.tool, args.get("cluster_id"), dump, pool)
                _write_capture_file(capture_dir, call_index, tool_plan.tool, args, ok, dump)
                records.append(_build_record(tool_plan.tool, args, ok, dump, err))
                await asyncio.sleep(_INTER_CALL_DELAY_SECONDS)
        namespace_total = sum(len(v) for v in pool.cluster_ns.values())
        print(
            f"wave {wave}: +{new_calls} calls (total {call_index}, "
            f"clusters {len(pool.clusters)}, ns {namespace_total}, families {len(pool.fam)})"
        )
        if new_calls == 0 or call_index >= CALL_CAP:
            break

    (repo_root / "capture_manifest.json").write_text(json.dumps(records, indent=2))
    return SweepOutcome(records, read_only_tools, pool)


def _write_capture_file(
    capture_dir: Path,
    call_index: int,
    tool: str,
    args: dict[str, str],
    ok: bool,
    dump: object,
) -> None:
    """Write one call's full response to its own JSON file."""

    sig = signature_key(args)
    byte_count = len(json.dumps(dump, default=str))
    document = {"tool": tool, "args": dict(args), "ok": ok, "bytes": byte_count, "dump": dump}
    (capture_dir / f"{call_index:04d}__{tool}__{sig}.json").write_text(
        json.dumps(document, indent=2, default=str)
    )


def _build_record(
    tool: str, args: dict[str, str], ok: bool, dump: object, err: str | None
) -> dict[str, Any]:
    """Build one manifest record summarizing a call's outcome."""

    record: dict[str, Any] = {
        "tool": tool,
        "args": dict(args),
        "ok": ok,
        "bytes": len(json.dumps(dump, default=str)),
        "top_keys": _top_level_keys(dump),
        "error_code": None if ok else err,
    }
    if ok:
        record["scan"] = scan_dump(dump)
    return record


def _top_level_keys(dump: object) -> list[str] | None:
    """Return a dict-shaped response's sorted top-level keys, else None."""

    if not isinstance(dump, dict):
        return None
    typed_dump = cast("dict[str, object]", dump)
    return sorted(typed_dump)
