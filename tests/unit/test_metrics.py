"""Tool-call metric emission tests.

Uses ``structlog.testing.capture_logs`` to assert on records emitted
by the dedicated ``rancher_mcp.metrics`` logger.
"""

from __future__ import annotations

import pytest
from _sdk_registry_support import placeholder_tool, registry_with
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherAPIError, RancherCapabilityError
from rancher_mcp.metrics import (
    MetricEntry,
    apply_metrics_to_all_tools,
    emit_metric,
    track_metric,
)
from rancher_mcp.sdk_registry import registered_tools


def test_emit_metric_writes_to_metrics_logger() -> None:
    """emit_metric should produce one structured metric record."""

    entry = MetricEntry(
        tool_name="rancher_demo",
        outcome="success",
        duration_ms=42,
    )
    with capture_logs() as logs:
        emit_metric(entry)

    [record] = logs
    assert record["event"] == "metric"
    assert record["log_level"] == "info"
    assert record["tool_name"] == "rancher_demo"
    assert record["outcome"] == "success"
    assert record["duration_ms"] == 42
    assert "error_code" not in record


@pytest.mark.asyncio
async def test_track_metric_success_emits_record() -> None:
    """A successful call emits one record with outcome=success."""

    @track_metric
    async def fake_tool() -> str:
        return "ok"

    with capture_logs() as logs:
        result = await fake_tool()

    assert result == "ok"
    [metric] = [r for r in logs if r.get("event") == "metric"]
    assert metric["outcome"] == "success"
    assert metric["tool_name"] == "fake_tool"
    assert metric["duration_ms"] >= 0
    assert "error_code" not in metric


@pytest.mark.asyncio
async def test_track_metric_capability_error_records_error_code() -> None:
    """RancherCapabilityError should produce outcome=error and propagate."""

    @track_metric
    async def fake_tool() -> None:
        raise RancherCapabilityError("read-only instance")

    with capture_logs() as logs, pytest.raises(RancherCapabilityError):
        await fake_tool()

    [metric] = [r for r in logs if r.get("event") == "metric"]
    assert metric["outcome"] == "error"
    assert metric["error_code"] == "CAPABILITY_ERROR"


@pytest.mark.asyncio
async def test_track_metric_api_error_records_error_code() -> None:
    """RancherAPIError should record API_ERROR error_code."""

    @track_metric
    async def fake_tool() -> None:
        raise RancherAPIError(404, "not found")

    with capture_logs() as logs, pytest.raises(RancherAPIError):
        await fake_tool()

    [metric] = [r for r in logs if r.get("event") == "metric"]
    assert metric["outcome"] == "error"
    assert metric["error_code"] == "API_ERROR"


@pytest.mark.asyncio
async def test_track_metric_passes_through_non_rancher_exceptions() -> None:
    """Non-RancherMCPError exceptions must NOT emit a metric record."""

    @track_metric
    async def fake_tool() -> None:
        raise ValueError("programming error")

    with capture_logs() as logs, pytest.raises(ValueError):
        await fake_tool()

    metrics = [r for r in logs if r.get("event") == "metric"]
    assert metrics == []


def test_apply_metrics_to_all_tools_wraps_each_tool_fn() -> None:
    """The bulk-apply helper should wrap every registered tool's fn."""

    mcp = registry_with("rancher_pods_list", "rancher_nodes_list")
    apply_metrics_to_all_tools(mcp)

    # Each tool.fn should now be a wrapped version (not the original itself).
    tools = registered_tools(mcp)
    assert len(tools) == 2
    for tool in tools:
        assert tool.fn is not placeholder_tool
        assert tool.fn.__wrapped__ is placeholder_tool  # functools.wraps preserves this
