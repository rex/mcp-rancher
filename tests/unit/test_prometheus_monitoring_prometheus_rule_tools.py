"""Curated PrometheusRule tool tests (list, get).

Covers PrometheusRule at ``monitoring.coreos.com/v1``.
"""

from __future__ import annotations

import pytest
from _prometheus_monitoring_support import (
    _PROMETHEUS_RULE_PAYLOAD,
    StubPrometheusMonitoringClient,
    build_settings,
)

from rancher_mcp.tools.prometheus_monitoring import (
    rancher_prometheus_rule_get,
    rancher_prometheus_rules_list,
)


@pytest.mark.asyncio
async def test_rancher_prometheus_rules_list_counts_alerts_and_recordings() -> None:
    """List should split rule_count into alert_count and recording_count."""

    result = await rancher_prometheus_rules_list(
        namespace="monitoring",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubPrometheusMonitoringClient(),
    )

    assert result.prometheus_rule_count == 1
    [rule] = result.prometheus_rules
    assert rule.name == "demo-rules"
    assert rule.group_count == 2
    assert rule.rule_count == 3
    assert rule.alert_count == 2
    assert rule.recording_count == 1


@pytest.mark.asyncio
async def test_rancher_prometheus_rule_get_returns_group_and_alert_names() -> None:
    """Detail should expose group_names and alert_names lists."""

    result = await rancher_prometheus_rule_get(
        namespace="monitoring",
        rule_name="demo-rules",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubPrometheusMonitoringClient(),
    )

    assert result.name == "demo-rules"
    assert result.group_names == ["node-alerts", "recording-rules"]
    assert result.alert_names == ["NodeDiskFull", "NodeMemoryHigh"]
    assert result.annotation_keys == ["team"]
    assert result.payload == _PROMETHEUS_RULE_PAYLOAD
