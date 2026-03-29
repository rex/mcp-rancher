"""Curated Rancher cluster role-template-binding tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.rbac import (
    RancherClusterRoleTemplateBindingDetail,
    RancherClusterRoleTemplateBindingList,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.rbac.shared import (
    binding_subject,
    build_query_params,
    cluster_role_template_binding_summary_from_payload,
    data_items,
    link_keys,
)


async def _fetch_cluster_role_template_bindings_list(
    instance_name: str,
    limit: int | None,
    cluster_id: str | None,
    role_template_id: str | None,
    user_id: str | None,
    user_principal_id: str | None,
    group_id: str | None,
    group_principal_id: str | None,
    namespace_id: str | None,
    name: str | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherClusterRoleTemplateBindingList:
    """Fetch and normalize the Rancher cluster role-template-binding collection."""

    query_params = build_query_params(
        limit=limit,
        clusterId=cluster_id,
        roleTemplateId=role_template_id,
        userId=user_id,
        userPrincipalId=user_principal_id,
        groupId=group_id,
        groupPrincipalId=group_principal_id,
        namespaceId=namespace_id,
        name=name,
        sort=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/clusterroletemplatebindings", params=query_params or None)
    bindings = [
        cluster_role_template_binding_summary_from_payload(item) for item in data_items(payload)
    ]
    return RancherClusterRoleTemplateBindingList(
        instance=instance_name,
        cluster_role_template_binding_count=len(bindings),
        applied_query_params=query_params,
        cluster_role_template_bindings=bindings,
    )


async def rancher_cluster_role_template_bindings_list(
    limit: int | None = None,
    cluster_id: str | None = None,
    role_template_id: str | None = None,
    user_id: str | None = None,
    user_principal_id: str | None = None,
    group_id: str | None = None,
    group_principal_id: str | None = None,
    namespace_id: str | None = None,
    name: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherClusterRoleTemplateBindingList:
    """List Rancher cluster role-template bindings with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cluster_role_template_bindings_list(
            instance_name,
            limit,
            cluster_id,
            role_template_id,
            user_id,
            user_principal_id,
            group_id,
            group_principal_id,
            namespace_id,
            name,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cluster_role_template_bindings_list(
            instance_name,
            limit,
            cluster_id,
            role_template_id,
            user_id,
            user_principal_id,
            group_id,
            group_principal_id,
            namespace_id,
            name,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_cluster_role_template_binding_get(
    cluster_role_template_binding_id: str,
    client: ManagementDiscoveryClient,
) -> RancherClusterRoleTemplateBindingDetail:
    """Fetch and normalize one Rancher cluster role-template binding."""

    payload = await client.get_json(
        f"/v3/clusterroletemplatebindings/{cluster_role_template_binding_id}"
    )
    subject_kind, subject_id = binding_subject(payload)
    return RancherClusterRoleTemplateBindingDetail.model_validate(payload).model_copy(
        update={
            "subject_kind": subject_kind,
            "subject_id": subject_id,
            "link_keys": link_keys(payload),
            "payload": dict(payload),
        }
    )


async def rancher_cluster_role_template_binding_get(
    cluster_role_template_binding_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherClusterRoleTemplateBindingDetail:
    """Fetch one Rancher cluster role-template binding by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cluster_role_template_binding_get(
            cluster_role_template_binding_id,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cluster_role_template_binding_get(
            cluster_role_template_binding_id,
            managed_client,
        )


async def rancher_cluster_role_template_bindings_list_tool(
    limit: int | None = None,
    cluster_id: str | None = None,
    role_template_id: str | None = None,
    user_id: str | None = None,
    user_principal_id: str | None = None,
    group_id: str | None = None,
    group_principal_id: str | None = None,
    namespace_id: str | None = None,
    name: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherClusterRoleTemplateBindingList:
    """Public MCP wrapper for curated cluster role-template-binding list."""

    return await rancher_cluster_role_template_bindings_list(
        limit=limit,
        cluster_id=cluster_id,
        role_template_id=role_template_id,
        user_id=user_id,
        user_principal_id=user_principal_id,
        group_id=group_id,
        group_principal_id=group_principal_id,
        namespace_id=namespace_id,
        name=name,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_cluster_role_template_binding_get_tool(
    cluster_role_template_binding_id: str,
    instance: str | None = None,
) -> RancherClusterRoleTemplateBindingDetail:
    """Public MCP wrapper for curated cluster role-template-binding detail."""

    return await rancher_cluster_role_template_binding_get(
        cluster_role_template_binding_id=cluster_role_template_binding_id,
        instance=instance,
    )
