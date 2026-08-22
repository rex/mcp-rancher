"""Curated ServiceMonitor tool tests (list, get).

Covers ServiceMonitor at ``monitoring.coreos.com/v1``.
"""

from __future__ import annotations

import pytest
from _prometheus_monitoring_support import (
    _SERVICE_MONITOR_PAYLOAD,
    StubPrometheusMonitoringClient,
    build_settings,
)

from rancher_mcp.tools.prometheus_monitoring import (
    rancher_service_monitor_get,
    rancher_service_monitors_list,
)


@pytest.mark.asyncio
async def test_rancher_service_monitors_list_returns_summary() -> None:
    """List should expose selector match labels, endpoint count, target namespaces."""

    result = await rancher_service_monitors_list(
        namespace="monitoring",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubPrometheusMonitoringClient(),
    )

    assert result.service_monitor_count == 1
    [sm] = result.service_monitors
    assert sm.name == "demo-svc-monitor"
    assert sm.selector_match_labels == {"app": "demo"}
    assert sm.endpoint_count == 2
    assert sm.target_namespaces == ["demo-app", "demo-staging"]
    assert sm.job_label == "demo-job"


@pytest.mark.asyncio
async def test_rancher_service_monitor_get_returns_endpoint_ports() -> None:
    """Detail should expose the sorted unique port list from spec.endpoints."""

    result = await rancher_service_monitor_get(
        namespace="monitoring",
        service_monitor_name="demo-svc-monitor",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubPrometheusMonitoringClient(),
    )

    assert result.name == "demo-svc-monitor"
    assert result.endpoint_ports == ["http-metrics", "telemetry"]
    assert result.payload == _SERVICE_MONITOR_PAYLOAD
