"""Tests for capture-sweep's human-readable summary report.

Pure string-building over synthetic records — no lab or crawl involved.
"""

from __future__ import annotations

from devtools.capture_sweep import Pool, build_report


def _ok_record(
    tool: str, byte_count: int, scan: dict[str, object] | None = None
) -> dict[str, object]:
    """Build a minimal successful capture record for report tests."""

    record: dict[str, object] = {
        "tool": tool,
        "args": {},
        "ok": True,
        "bytes": byte_count,
        "top_keys": None,
        "error_code": None,
    }
    if scan is not None:
        record["scan"] = scan
    return record


def _error_record(tool: str, error_code: str) -> dict[str, object]:
    """Build a minimal failed capture record for report tests."""

    return {
        "tool": tool,
        "args": {},
        "ok": False,
        "bytes": 0,
        "top_keys": None,
        "error_code": error_code,
    }


def test_build_report_counts_ok_and_error_calls() -> None:
    """The ok/error tally line should reflect exactly what was passed in."""

    records = [
        _ok_record("rancher_clusters_list", 100),
        _error_record("rancher_node_get", "NOT_FOUND"),
    ]

    text = build_report(records, frozenset({"rancher_clusters_list", "rancher_node_get"}), Pool())

    assert "ok: 1  errors: 1" in text


def test_build_report_lists_never_exercised_read_only_tools() -> None:
    """A read-only tool with no matching record should show up as never-run."""

    records = [_ok_record("rancher_clusters_list", 100)]
    read_only = frozenset({"rancher_clusters_list", "rancher_nodes_list"})

    text = build_report(records, read_only, Pool())

    assert "READ-ONLY TOOLS NEVER EXERCISED (1)" in text
    assert "nodes_list" in text


def test_build_report_surfaces_residual_plumbing_leaks() -> None:
    """A record whose scan found plumbing keys should be counted as a leak."""

    scan = {"plumbing": ["uid"], "long_strings": [], "redacted": 0, "base64ish": []}
    records = [_ok_record("rancher_cluster_get", 50, scan=scan)]

    text = build_report(records, frozenset({"rancher_cluster_get"}), Pool())

    assert "RESIDUAL PLUMBING LEAKS (L-0 miss): 1" in text


def test_build_report_includes_discovery_counts_from_the_pool() -> None:
    """The discovery line should reflect the pool's clusters/namespaces, not the records."""

    pool = Pool()
    pool.add_cluster("c-1")
    pool.add_ns("c-1", "default")

    text = build_report([], frozenset(), pool)

    assert "discovery: 1 clusters, 1 namespaces" in text


def test_build_report_omits_the_size_histogram_when_there_are_no_ok_records() -> None:
    """With zero successful calls there is nothing to summarize sizes for."""

    text = build_report([_error_record("rancher_node_get", "NOT_FOUND")], frozenset(), Pool())

    assert "response bytes" not in text
