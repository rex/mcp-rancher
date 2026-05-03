"""Curated Rancher cluster alert rule tools."""

from __future__ import annotations

from typing import cast

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.alerts import (
    RancherAlertRuleDetail,
    RancherAlertRuleList,
    RancherAlertRuleSummary,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.support.values import mapping_value


def _data_items(payload: dict[str, object]) -> list[dict[str, object]]:
    raw = payload.get("data")
    if not isinstance(raw, list):
        return []
    return [item for item in cast(list[object], raw) if isinstance(item, dict)]


async def _fetch_cluster_alert_rules_list(
    instance_name: str,
    limit: int | None,
    cluster_id: str | None,
    severity: str | None,
    state: str | None,
    client: ManagementDiscoveryClient,
) -> RancherAlertRuleList:
    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if severity is not None:
        params["severity"] = severity
    if state is not None:
        params["state"] = state
    payload = await client.get_json("/v3/clusteralertrules", params=params or None)
    rules = [RancherAlertRuleSummary.model_validate(item) for item in _data_items(payload)]
    return RancherAlertRuleList(
        instance=instance_name,
        alert_rule_count=len(rules),
        applied_query_params=params,
        alert_rules=rules,
    )


async def rancher_cluster_alert_rules_list(
    limit: int | None = None,
    cluster_id: str | None = None,
    severity: str | None = None,
    state: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherAlertRuleList:
    """List Rancher cluster alert rules."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cluster_alert_rules_list(
            instance_name, limit, cluster_id, severity, state, client
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cluster_alert_rules_list(
            instance_name, limit, cluster_id, severity, state, managed_client
        )


async def _fetch_cluster_alert_rule_get(
    rule_id: str,
    client: ManagementDiscoveryClient,
) -> RancherAlertRuleDetail:
    payload = await client.get_json(f"/v3/clusteralertrules/{rule_id}")
    status = mapping_value(payload, "status") or {}
    base = RancherAlertRuleDetail.model_validate(payload)
    return base.model_copy(update={"status": dict(status), "payload": dict(payload)})


async def rancher_cluster_alert_rule_get(
    rule_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherAlertRuleDetail:
    """Fetch one Rancher cluster alert rule by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cluster_alert_rule_get(rule_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cluster_alert_rule_get(rule_id, managed_client)


async def rancher_cluster_alert_rules_list_tool(
    limit: int | None = None,
    cluster_id: str | None = None,
    severity: str | None = None,
    state: str | None = None,
    instance: str | None = None,
) -> RancherAlertRuleList:
    """List Rancher cluster alert rules (critical, warning, info)."""

    return await rancher_cluster_alert_rules_list(
        limit=limit, cluster_id=cluster_id, severity=severity, state=state, instance=instance
    )


async def rancher_cluster_alert_rule_get_tool(
    rule_id: str,
    instance: str | None = None,
) -> RancherAlertRuleDetail:
    """Fetch one Rancher cluster alert rule by id."""

    return await rancher_cluster_alert_rule_get(rule_id=rule_id, instance=instance)
