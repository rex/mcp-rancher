"""Human-readable capture-sweep report: sizes, plumbing scan, coverage.

Pure string building over already-computed data (the crawl's records,
the read-only tool name set, and the final discovery pool) — no lab or
network access, so it's cheap to feed synthetic data in tests.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from devtools.capture_sweep.pool import Pool

_TOP_N_LARGEST = 25
_BIG_RESPONSE_BYTES = 8_000
_HUGE_RESPONSE_BYTES = 20_000
_MAX_LISTED_LEAKS = 20
_MAX_LISTED_LONG_STRINGS = 20


def build_report(records: list[dict[str, Any]], read_only_tools: frozenset[str], pool: Pool) -> str:
    """Render the final sweep report: sizes, plumbing scan, coverage, errors."""

    ok_records = [record for record in records if record["ok"]]
    error_records = [record for record in records if not record["ok"]]
    ran_tools = {record["tool"] for record in records}
    never_ran = sorted(read_only_tools - ran_tools)
    sizes = sorted((record["bytes"] for record in ok_records), reverse=True)

    lines: list[str] = [
        "=" * 72,
        f"CAPTURE COMPLETE — {len(records)} calls written to ./capture",
        _discovery_line(pool),
        f"read-only tools exercised: {len(ran_tools & read_only_tools)}/{len(read_only_tools)}"
        f"   (never ran: {len(never_ran)})",
        f"ok: {len(ok_records)}  errors: {len(error_records)}",
    ]
    if sizes:
        lines.append(
            f"response bytes  min={sizes[-1]}  median={int(median(sizes))}  "
            f"p90={sizes[int(len(sizes) * 0.1)]}  max={sizes[0]}"
        )

    lines += _largest_responses_section(ok_records)
    lines += _bloat_threshold_section(ok_records)
    lines += _plumbing_leaks_section(ok_records)
    lines += _long_strings_section(ok_records)
    lines += _never_exercised_section(never_ran)
    lines += _error_codes_section(error_records)
    return "\n".join(lines)


def write_report(text: str, capture_dir: Path) -> Path:
    """Write the report to ``<capture_dir>/SUMMARY.md`` in addition to stdout."""

    path = capture_dir / "SUMMARY.md"
    path.write_text(text + "\n", encoding="utf-8")
    return path


def _scan_of(record: dict[str, Any]) -> dict[str, Any]:
    """Return one record's scan findings, or an empty-but-typed fallback."""

    scan: dict[str, Any] = record.get("scan") or {}
    return scan


def _discovery_line(pool: Pool) -> str:
    """Summarize how many clusters/namespaces/families the sweep discovered."""

    namespace_total = sum(len(namespaces) for namespaces in pool.cluster_ns.values())
    return (
        f"discovery: {len(pool.clusters)} clusters, {namespace_total} namespaces, "
        f"{len(pool.fam)} resource families"
    )


def _largest_responses_section(ok_records: list[dict[str, Any]]) -> list[str]:
    """List the N largest successful responses with any scan findings."""

    lines = ["", f"--- TOP {_TOP_N_LARGEST} LARGEST ok responses ---"]
    largest = sorted(ok_records, key=lambda record: -record["bytes"])[:_TOP_N_LARGEST]
    for record in largest:
        scan = _scan_of(record)
        extra: list[str] = []
        if scan.get("plumbing"):
            extra.append(f"PLUMBING={scan['plumbing']}")
        if scan.get("long_strings"):
            extra.append(f"longstr={len(scan['long_strings'])}")
        lines.append(
            f"  {record['bytes']:7d}B  {record['tool']}  {record['args']}  {' '.join(extra)}"
        )
    return lines


def _bloat_threshold_section(ok_records: list[dict[str, Any]]) -> list[str]:
    """Count responses over the big/huge byte thresholds."""

    big = sum(1 for record in ok_records if record["bytes"] > _BIG_RESPONSE_BYTES)
    huge = sum(1 for record in ok_records if record["bytes"] > _HUGE_RESPONSE_BYTES)
    big_kb, huge_kb = _BIG_RESPONSE_BYTES // 1000, _HUGE_RESPONSE_BYTES // 1000
    return ["", f">{big_kb}KB responses: {big}   >{huge_kb}KB: {huge}"]


def _plumbing_leaks_section(ok_records: list[dict[str, Any]]) -> list[str]:
    """List responses carrying residual plumbing the L-0 serializer should strip."""

    leaks = [
        (record["tool"], record["args"], _scan_of(record)["plumbing"])
        for record in ok_records
        if _scan_of(record).get("plumbing")
    ]
    lines = ["", f"--- RESIDUAL PLUMBING LEAKS (L-0 miss): {len(leaks)} ---"]
    for tool, args, plumbing in leaks[:_MAX_LISTED_LEAKS]:
        lines.append(f"  {tool} {args}: {plumbing}")
    return lines


def _long_strings_section(ok_records: list[dict[str, Any]]) -> list[str]:
    """List responses with inline strings long enough to be shaping candidates."""

    long_strings = [
        (record["tool"], record["args"], _scan_of(record)["long_strings"])
        for record in ok_records
        if _scan_of(record).get("long_strings")
    ]
    lines = ["", f"--- LONG INLINE STRINGS >800B (shaping candidates): {len(long_strings)} ---"]
    for tool, args, strings in long_strings[:_MAX_LISTED_LONG_STRINGS]:
        lines.append(f"  {tool} {args}: {strings[:3]}")
    return lines


def _never_exercised_section(never_ran: list[str]) -> list[str]:
    """List every read-only tool the sweep never managed to satisfy."""

    lines = ["", f"--- READ-ONLY TOOLS NEVER EXERCISED ({len(never_ran)}) ---"]
    lines.append("  " + "  ".join(tool.removeprefix("rancher_") for tool in never_ran))
    return lines


def _error_codes_section(error_records: list[dict[str, Any]]) -> list[str]:
    """Summarize error records by error_code, most common first."""

    codes = Counter(record["error_code"] for record in error_records)
    lines = ["", f"--- ERROR CODES ({len(error_records)}) ---"]
    for code, count in codes.most_common():
        lines.append(f"  {count:3d}  {code}")
    return lines
