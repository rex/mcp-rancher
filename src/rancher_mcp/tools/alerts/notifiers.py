"""Curated Rancher notifier tools."""

from __future__ import annotations

from typing import cast

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.alerts import (
    RancherNotifierDetail,
    RancherNotifierList,
    RancherNotifierSummary,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.support.values import mapping_value

_NOTIFIER_CONFIG_KEYS = (
    "slackConfig",
    "emailConfig",
    "pagerdutyConfig",
    "webhookConfig",
    "dingtalkConfig",
    "msteamsConfig",
    "wechatConfig",
)


def _notifier_types(payload: dict[str, object]) -> list[str]:
    return [k.removesuffix("Config") for k in _NOTIFIER_CONFIG_KEYS if payload.get(k)]


def _data_items(payload: dict[str, object]) -> list[dict[str, object]]:
    raw = payload.get("data")
    if not isinstance(raw, list):
        return []
    return [item for item in cast(list[object], raw) if isinstance(item, dict)]


def _notifier_summary(item: dict[str, object]) -> RancherNotifierSummary:
    base = RancherNotifierSummary.model_validate(item)
    return base.model_copy(update={"notifier_types": _notifier_types(item)})


async def _fetch_notifiers_list(
    instance_name: str,
    limit: int | None,
    cluster_id: str | None,
    state: str | None,
    client: ManagementDiscoveryClient,
) -> RancherNotifierList:
    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if state is not None:
        params["state"] = state
    payload = await client.get_json("/v3/notifiers", params=params or None)
    notifiers = [_notifier_summary(item) for item in _data_items(payload)]
    return RancherNotifierList(
        instance=instance_name,
        notifier_count=len(notifiers),
        applied_query_params=params,
        notifiers=notifiers,
    )


async def rancher_notifiers_list(
    limit: int | None = None,
    cluster_id: str | None = None,
    state: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherNotifierList:
    """List Rancher notifiers (Slack, email, PagerDuty, webhook, etc.)."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_notifiers_list(instance_name, limit, cluster_id, state, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_notifiers_list(instance_name, limit, cluster_id, state, managed_client)


async def _fetch_notifier_get(
    notifier_id: str,
    client: ManagementDiscoveryClient,
) -> RancherNotifierDetail:
    payload = await client.get_json(f"/v3/notifiers/{notifier_id}")
    status = mapping_value(payload, "status") or {}
    actions = mapping_value(payload, "actions") or {}
    links = mapping_value(payload, "links") or {}
    base = RancherNotifierDetail.model_validate(payload)
    return base.model_copy(
        update={
            "notifier_types": _notifier_types(payload),
            "status": dict(status),
            "action_keys": sorted(actions.keys()),
            "link_keys": sorted(links.keys()),
            "payload": dict(payload),
        }
    )


async def rancher_notifier_get(
    notifier_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherNotifierDetail:
    """Fetch one Rancher notifier by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_notifier_get(notifier_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_notifier_get(notifier_id, managed_client)


async def rancher_notifiers_list_tool(
    limit: int | None = None,
    cluster_id: str | None = None,
    state: str | None = None,
    instance: str | None = None,
) -> RancherNotifierList:
    """List Rancher notifiers configured for a cluster."""

    return await rancher_notifiers_list(
        limit=limit, cluster_id=cluster_id, state=state, instance=instance
    )


async def rancher_notifier_get_tool(
    notifier_id: str,
    instance: str | None = None,
) -> RancherNotifierDetail:
    """Fetch one Rancher notifier by id."""

    return await rancher_notifier_get(notifier_id=notifier_id, instance=instance)
