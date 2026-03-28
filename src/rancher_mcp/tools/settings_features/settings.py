# pyright: reportPrivateUsage=false
"""Curated Rancher setting tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.settings_features import RancherSettingDetail, RancherSettingList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.settings_features.shared import (
    _build_settings_query_params,
    _data_items,
    _setting_summary_from_payload,
)


async def _fetch_settings_list(
    instance_name: str,
    limit: int | None,
    source: str | None,
    customized: bool | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherSettingList:
    """Fetch and normalize the Rancher settings collection."""

    query_params = _build_settings_query_params(
        limit=limit,
        source=source,
        customized=customized,
        sort_by=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/settings", params=query_params or None)
    settings = [_setting_summary_from_payload(item) for item in _data_items(payload)]
    return RancherSettingList(
        instance=instance_name,
        setting_count=len(settings),
        applied_query_params=query_params,
        settings=settings,
    )


async def rancher_settings_list(
    limit: int | None = None,
    source: str | None = None,
    customized: bool | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherSettingList:
    """List Rancher settings with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_settings_list(
            instance_name,
            limit,
            source,
            customized,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_settings_list(
            instance_name,
            limit,
            source,
            customized,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_setting_get(
    instance_name: str,
    setting_id: str,
    client: ManagementDiscoveryClient,
) -> RancherSettingDetail:
    """Fetch and normalize one Rancher setting."""

    payload = await client.get_json(f"/v3/settings/{setting_id}")
    summary = _setting_summary_from_payload(payload)
    return RancherSettingDetail(
        id=summary.id,
        name=summary.name,
        value=summary.value,
        default=summary.default,
        source=summary.source,
        customized=summary.customized,
        payload=dict(payload),
    )


async def rancher_setting_get(
    setting_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherSettingDetail:
    """Fetch one Rancher setting by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_setting_get(instance_name, setting_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_setting_get(instance_name, setting_id, managed_client)


async def rancher_settings_list_tool(
    limit: int | None = None,
    source: str | None = None,
    customized: bool | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherSettingList:
    """Public MCP wrapper for curated settings list."""

    return await rancher_settings_list(
        limit=limit,
        source=source,
        customized=customized,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_setting_get_tool(
    setting_id: str,
    instance: str | None = None,
) -> RancherSettingDetail:
    """Public MCP wrapper for curated setting detail."""

    return await rancher_setting_get(
        setting_id=setting_id,
        instance=instance,
    )
