"""Curated Rancher global-role tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.rbac import RancherGlobalRoleDetail, RancherGlobalRoleList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.rbac.shared import (
    action_keys,
    build_query_params,
    data_items,
    global_role_summary_from_payload,
    link_keys,
)


async def _fetch_global_roles_list(
    instance_name: str,
    limit: int | None,
    builtin: bool | None,
    name: str | None,
    new_user_default: bool | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherGlobalRoleList:
    """Fetch and normalize the Rancher global-role collection."""

    query_params = build_query_params(
        limit=limit,
        builtin=builtin,
        name=name,
        newUserDefault=new_user_default,
        sort=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/globalroles", params=query_params or None)
    global_roles = [global_role_summary_from_payload(item) for item in data_items(payload)]
    return RancherGlobalRoleList(
        instance=instance_name,
        global_role_count=len(global_roles),
        applied_query_params=query_params,
        global_roles=global_roles,
    )


async def rancher_global_roles_list(
    limit: int | None = None,
    builtin: bool | None = None,
    name: str | None = None,
    new_user_default: bool | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherGlobalRoleList:
    """List Rancher global roles with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_global_roles_list(
            instance_name,
            limit,
            builtin,
            name,
            new_user_default,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_global_roles_list(
            instance_name,
            limit,
            builtin,
            name,
            new_user_default,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_global_role_get(
    global_role_id: str,
    client: ManagementDiscoveryClient,
) -> RancherGlobalRoleDetail:
    """Fetch and normalize one Rancher global role."""

    payload = await client.get_json(f"/v3/globalroles/{global_role_id}")
    detail = RancherGlobalRoleDetail.model_validate(payload)
    return detail.model_copy(
        update={
            "rule_count": len(detail.rules),
            "action_keys": action_keys(payload),
            "link_keys": link_keys(payload),
            "payload": dict(payload),
        }
    )


async def rancher_global_role_get(
    global_role_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherGlobalRoleDetail:
    """Fetch one Rancher global role by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_global_role_get(global_role_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_global_role_get(global_role_id, managed_client)


async def rancher_global_roles_list_tool(
    limit: int | None = None,
    builtin: bool | None = None,
    name: str | None = None,
    new_user_default: bool | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherGlobalRoleList:
    """Public MCP wrapper for curated global-role list."""

    return await rancher_global_roles_list(
        limit=limit,
        builtin=builtin,
        name=name,
        new_user_default=new_user_default,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_global_role_get_tool(
    global_role_id: str,
    instance: str | None = None,
) -> RancherGlobalRoleDetail:
    """Public MCP wrapper for curated global-role detail."""

    return await rancher_global_role_get(global_role_id=global_role_id, instance=instance)
