"""Curated Rancher Fleet workspace tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.fleet_registration import (
    RancherFleetWorkspaceDetail,
    RancherFleetWorkspaceList,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.fleet_registration.shared import (
    action_keys,
    build_query_params,
    data_items,
    fleet_workspace_summary_from_payload,
    link_keys,
)
from rancher_mcp.tools.support.values import mapping_value


async def _fetch_fleet_workspaces_list(
    instance_name: str,
    limit: int | None,
    name: str | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherFleetWorkspaceList:
    """Fetch and normalize the Rancher Fleet workspace collection."""

    query_params = build_query_params(
        limit=limit,
        name=name,
        sort=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/fleetworkspaces", params=query_params or None)
    fleet_workspaces = [fleet_workspace_summary_from_payload(item) for item in data_items(payload)]
    return RancherFleetWorkspaceList(
        instance=instance_name,
        fleet_workspace_count=len(fleet_workspaces),
        applied_query_params=query_params,
        fleet_workspaces=fleet_workspaces,
    )


async def rancher_fleet_workspaces_list(
    limit: int | None = None,
    name: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherFleetWorkspaceList:
    """List Rancher Fleet workspaces with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_fleet_workspaces_list(
            instance_name,
            limit,
            name,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_fleet_workspaces_list(
            instance_name,
            limit,
            name,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_fleet_workspace_get(
    fleet_workspace_id: str,
    client: ManagementDiscoveryClient,
) -> RancherFleetWorkspaceDetail:
    """Fetch and normalize one Rancher Fleet workspace."""

    payload = await client.get_json(f"/v3/fleetworkspaces/{fleet_workspace_id}")
    detail = RancherFleetWorkspaceDetail.model_validate(payload)
    return detail.model_copy(
        update={
            "status_keys": sorted((mapping_value(payload, "status") or {}).keys()),
            "action_keys": action_keys(payload),
            "link_keys": link_keys(payload),
            "payload": dict(payload),
        }
    )


async def rancher_fleet_workspace_get(
    fleet_workspace_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherFleetWorkspaceDetail:
    """Fetch one Rancher Fleet workspace by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_fleet_workspace_get(fleet_workspace_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_fleet_workspace_get(fleet_workspace_id, managed_client)


async def rancher_fleet_workspaces_list_tool(
    limit: int | None = None,
    name: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherFleetWorkspaceList:
    """Public MCP wrapper for curated Fleet workspace list."""

    return await rancher_fleet_workspaces_list(
        limit=limit,
        name=name,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_fleet_workspace_get_tool(
    fleet_workspace_id: str,
    instance: str | None = None,
) -> RancherFleetWorkspaceDetail:
    """Public MCP wrapper for curated Fleet workspace detail."""

    return await rancher_fleet_workspace_get(
        fleet_workspace_id=fleet_workspace_id,
        instance=instance,
    )
