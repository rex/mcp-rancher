"""Curated Rancher group tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.auth_identity import RancherGroupDetail, RancherGroupList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.auth_identity.shared import (
    build_group_query_params,
    data_items,
    group_summary_from_payload,
)
from rancher_mcp.tools.support.values import mapping_value


async def _fetch_groups_list(
    instance_name: str,
    limit: int | None,
    name: str | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherGroupList:
    """Fetch and normalize the Rancher groups collection."""

    query_params = build_group_query_params(
        limit=limit,
        name=name,
        sort_by=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/groups", params=query_params or None)
    groups = [group_summary_from_payload(item) for item in data_items(payload)]
    return RancherGroupList(
        instance=instance_name,
        group_count=len(groups),
        applied_query_params=query_params,
        groups=groups,
    )


async def rancher_groups_list(
    limit: int | None = None,
    name: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherGroupList:
    """List Rancher groups with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_groups_list(
            instance_name,
            limit,
            name,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_groups_list(
            instance_name,
            limit,
            name,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_group_get(
    group_id: str,
    client: ManagementDiscoveryClient,
) -> RancherGroupDetail:
    """Fetch and normalize one Rancher group."""

    payload = await client.get_json(f"/v3/groups/{group_id}")
    return RancherGroupDetail.model_validate(payload).model_copy(
        update={
            "link_keys": sorted(mapping_value(payload, "links") or {}),
            "payload": dict(payload),
        }
    )


async def rancher_group_get(
    group_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherGroupDetail:
    """Fetch one Rancher group by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_group_get(group_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_group_get(group_id, managed_client)


async def rancher_groups_list_tool(
    limit: int | None = None,
    name: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherGroupList:
    """Public MCP wrapper for curated groups list."""

    return await rancher_groups_list(
        limit=limit,
        name=name,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_group_get_tool(
    group_id: str,
    instance: str | None = None,
) -> RancherGroupDetail:
    """Public MCP wrapper for curated group detail."""

    return await rancher_group_get(group_id=group_id, instance=instance)
