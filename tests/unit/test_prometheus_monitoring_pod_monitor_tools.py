"""Curated PodMonitor tool tests (list, get).

Covers PodMonitor at ``monitoring.coreos.com/v1``.
"""

from __future__ import annotations

import pytest
from _prometheus_monitoring_support import (
    _POD_MONITOR_PAYLOAD,
    StubPrometheusMonitoringClient,
    build_settings,
)

from rancher_mcp.tools.prometheus_monitoring import (
    rancher_pod_monitor_get,
    rancher_pod_monitors_list,
)


@pytest.mark.asyncio
async def test_rancher_pod_monitors_list_returns_summary() -> None:
    """List should expose podMetricsEndpoints count and target namespaces."""

    result = await rancher_pod_monitors_list(
        namespace="monitoring",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubPrometheusMonitoringClient(),
    )

    assert result.pod_monitor_count == 1
    [pm] = result.pod_monitors
    assert pm.name == "demo-pod-monitor"
    assert pm.selector_match_labels == {"role": "worker"}
    assert pm.endpoint_count == 1
    assert pm.target_namespaces == ["demo-app"]
    assert pm.job_label == "demo-pods"


@pytest.mark.asyncio
async def test_rancher_pod_monitor_get_returns_endpoint_ports() -> None:
    """Detail should expose the sorted unique port list from spec.podMetricsEndpoints."""

    result = await rancher_pod_monitor_get(
        namespace="monitoring",
        pod_monitor_name="demo-pod-monitor",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubPrometheusMonitoringClient(),
    )

    assert result.name == "demo-pod-monitor"
    assert result.endpoint_ports == ["metrics"]
    assert result.payload == _POD_MONITOR_PAYLOAD
