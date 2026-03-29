"""Curated Rancher global-role-binding tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.rbac import RancherGlobalRoleBindingDetail, RancherGlobalRoleBindingList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.rbac.shared import (
    binding_subject,
    build_query_params,
    data_items,
    global_role_binding_summary_from_payload,
    link_keys,
)


async def _fetch_global_role_bindings_list(
    instance_name: str,
    limit: int | None,
    global_role_id: str | None,
    user_id: str | None,
    group_principal_id: str | None,
    name: str | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherGlobalRoleBindingList:
    """Fetch and normalize the Rancher global-role-binding collection."""

    query_params = build_query_params(
        limit=limit,
        globalRoleId=global_role_id,
        userId=user_id,
        groupPrincipalId=group_principal_id,
        name=name,
        sort=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/globalrolebindings", params=query_params or None)
    bindings = [global_role_binding_summary_from_payload(item) for item in data_items(payload)]
    return RancherGlobalRoleBindingList(
        instance=instance_name,
        global_role_binding_count=len(bindings),
        applied_query_params=query_params,
        global_role_bindings=bindings,
    )


async def rancher_global_role_bindings_list(
    limit: int | None = None,
    global_role_id: str | None = None,
    user_id: str | None = None,
    group_principal_id: str | None = None,
    name: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherGlobalRoleBindingList:
    """List Rancher global role bindings with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_global_role_bindings_list(
            instance_name,
            limit,
            global_role_id,
            user_id,
            group_principal_id,
            name,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_global_role_bindings_list(
            instance_name,
            limit,
            global_role_id,
            user_id,
            group_principal_id,
            name,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_global_role_binding_get(
    global_role_binding_id: str,
    client: ManagementDiscoveryClient,
) -> RancherGlobalRoleBindingDetail:
    """Fetch and normalize one Rancher global role binding."""

    payload = await client.get_json(f"/v3/globalrolebindings/{global_role_binding_id}")
    subject_kind, subject_id = binding_subject(payload)
    return RancherGlobalRoleBindingDetail.model_validate(payload).model_copy(
        update={
            "subject_kind": subject_kind,
            "subject_id": subject_id,
            "link_keys": link_keys(payload),
            "payload": dict(payload),
        }
    )


async def rancher_global_role_binding_get(
    global_role_binding_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherGlobalRoleBindingDetail:
    """Fetch one Rancher global role binding by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_global_role_binding_get(global_role_binding_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_global_role_binding_get(global_role_binding_id, managed_client)


async def rancher_global_role_bindings_list_tool(
    limit: int | None = None,
    global_role_id: str | None = None,
    user_id: str | None = None,
    group_principal_id: str | None = None,
    name: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherGlobalRoleBindingList:
    """Public MCP wrapper for curated global-role-binding list."""

    return await rancher_global_role_bindings_list(
        limit=limit,
        global_role_id=global_role_id,
        user_id=user_id,
        group_principal_id=group_principal_id,
        name=name,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_global_role_binding_get_tool(
    global_role_binding_id: str,
    instance: str | None = None,
) -> RancherGlobalRoleBindingDetail:
    """Public MCP wrapper for curated global-role-binding detail."""

    return await rancher_global_role_binding_get(
        global_role_binding_id=global_role_binding_id,
        instance=instance,
    )
