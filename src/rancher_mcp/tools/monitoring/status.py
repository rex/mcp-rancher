"""Rancher cluster monitoring status tool."""

from __future__ import annotations

from typing import cast

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.monitoring import RancherMonitoringStatus
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.support.values import mapping_value, string_value


def _monitoring_status_from_cluster(
    instance_name: str,
    cluster_id: str,
    payload: dict[str, object],
) -> RancherMonitoringStatus:
    """Extract monitoring status fields from a cluster payload."""

    monitoring_status = mapping_value(payload, "monitoringStatus") or {}
    conditions_raw = monitoring_status.get("conditions")
    conditions: list[dict[str, object]] = (
        [c for c in cast(list[object], conditions_raw) if isinstance(c, dict)]
        if isinstance(conditions_raw, list)
        else []
    )
    state: str | None = None
    for cond in conditions:
        if string_value(cond, "type") == "Available":
            state = "active" if string_value(cond, "status") == "True" else "unavailable"
            break

    return RancherMonitoringStatus(
        instance=instance_name,
        cluster_id=cluster_id,
        monitoring_enabled=bool(payload.get("enableClusterMonitoring")),
        state=state,
        grafana_endpoint=string_value(monitoring_status, "grafanaEndpoint"),
        prometheus_endpoint=string_value(monitoring_status, "prometheusEndpoint"),
        conditions=conditions,
        payload=dict(monitoring_status),
    )


async def _fetch_monitoring_status(
    instance_name: str,
    cluster_id: str,
    client: ManagementDiscoveryClient,
) -> RancherMonitoringStatus:
    payload = await client.get_json(f"/v3/clusters/{cluster_id}")
    return _monitoring_status_from_cluster(instance_name, cluster_id, payload)


async def rancher_monitoring_status(
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherMonitoringStatus:
    """Fetch monitoring enabled/disabled status and endpoint summary for a cluster."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_monitoring_status(instance_name, cluster_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_monitoring_status(instance_name, cluster_id, managed_client)


async def rancher_monitoring_status_tool(
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherMonitoringStatus:
    """Check if Rancher monitoring is enabled on a cluster and summarize its state."""

    return await rancher_monitoring_status(cluster_id=cluster_id, instance=instance)
