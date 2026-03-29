"""Curated Rancher auth-config tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.auth_identity import RancherAuthConfigDetail, RancherAuthConfigList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.auth_identity.shared import (
    auth_config_summary_from_payload,
    build_auth_config_query_params,
    data_items,
)
from rancher_mcp.tools.support.values import mapping_value


async def _fetch_auth_configs_list(
    instance_name: str,
    limit: int | None,
    enabled: bool | None,
    provider_type: str | None,
    access_mode: str | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherAuthConfigList:
    """Fetch and normalize the Rancher auth-config collection."""

    query_params = build_auth_config_query_params(
        limit=limit,
        enabled=enabled,
        provider_type=provider_type,
        access_mode=access_mode,
        sort_by=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/authconfigs", params=query_params or None)
    auth_configs = [auth_config_summary_from_payload(item) for item in data_items(payload)]
    return RancherAuthConfigList(
        instance=instance_name,
        auth_config_count=len(auth_configs),
        applied_query_params=query_params,
        auth_configs=auth_configs,
    )


async def rancher_auth_configs_list(
    limit: int | None = None,
    enabled: bool | None = None,
    provider_type: str | None = None,
    access_mode: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherAuthConfigList:
    """List Rancher auth configs with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_auth_configs_list(
            instance_name,
            limit,
            enabled,
            provider_type,
            access_mode,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_auth_configs_list(
            instance_name,
            limit,
            enabled,
            provider_type,
            access_mode,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_auth_config_get(
    auth_config_id: str,
    client: ManagementDiscoveryClient,
) -> RancherAuthConfigDetail:
    """Fetch and normalize one Rancher auth config."""

    payload = await client.get_json(f"/v3/authconfigs/{auth_config_id}")
    return RancherAuthConfigDetail.model_validate(payload).model_copy(
        update={
            "action_keys": sorted(mapping_value(payload, "actions") or {}),
            "link_keys": sorted(mapping_value(payload, "links") or {}),
            "payload": dict(payload),
        }
    )


async def rancher_auth_config_get(
    auth_config_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherAuthConfigDetail:
    """Fetch one Rancher auth config by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_auth_config_get(auth_config_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_auth_config_get(auth_config_id, managed_client)


async def rancher_auth_configs_list_tool(
    limit: int | None = None,
    enabled: bool | None = None,
    provider_type: str | None = None,
    access_mode: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherAuthConfigList:
    """Public MCP wrapper for curated auth-config list."""

    return await rancher_auth_configs_list(
        limit=limit,
        enabled=enabled,
        provider_type=provider_type,
        access_mode=access_mode,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_auth_config_get_tool(
    auth_config_id: str,
    instance: str | None = None,
) -> RancherAuthConfigDetail:
    """Public MCP wrapper for curated auth-config detail."""

    return await rancher_auth_config_get(auth_config_id=auth_config_id, instance=instance)
