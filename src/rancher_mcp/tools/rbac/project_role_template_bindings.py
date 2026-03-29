"""Curated Rancher project role-template-binding tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.rbac import (
    RancherProjectRoleTemplateBindingDetail,
    RancherProjectRoleTemplateBindingList,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.rbac.shared import (
    binding_subject,
    build_query_params,
    data_items,
    link_keys,
    project_role_template_binding_summary_from_payload,
)


async def _fetch_project_role_template_bindings_list(
    instance_name: str,
    limit: int | None,
    project_id: str | None,
    role_template_id: str | None,
    user_id: str | None,
    user_principal_id: str | None,
    group_id: str | None,
    group_principal_id: str | None,
    namespace_id: str | None,
    service_account: str | None,
    name: str | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherProjectRoleTemplateBindingList:
    """Fetch and normalize the Rancher project role-template-binding collection."""

    query_params = build_query_params(
        limit=limit,
        projectId=project_id,
        roleTemplateId=role_template_id,
        userId=user_id,
        userPrincipalId=user_principal_id,
        groupId=group_id,
        groupPrincipalId=group_principal_id,
        namespaceId=namespace_id,
        serviceAccount=service_account,
        name=name,
        sort=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/projectroletemplatebindings", params=query_params or None)
    bindings = [
        project_role_template_binding_summary_from_payload(item) for item in data_items(payload)
    ]
    return RancherProjectRoleTemplateBindingList(
        instance=instance_name,
        project_role_template_binding_count=len(bindings),
        applied_query_params=query_params,
        project_role_template_bindings=bindings,
    )


async def rancher_project_role_template_bindings_list(
    limit: int | None = None,
    project_id: str | None = None,
    role_template_id: str | None = None,
    user_id: str | None = None,
    user_principal_id: str | None = None,
    group_id: str | None = None,
    group_principal_id: str | None = None,
    namespace_id: str | None = None,
    service_account: str | None = None,
    name: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherProjectRoleTemplateBindingList:
    """List Rancher project role-template bindings with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_project_role_template_bindings_list(
            instance_name,
            limit,
            project_id,
            role_template_id,
            user_id,
            user_principal_id,
            group_id,
            group_principal_id,
            namespace_id,
            service_account,
            name,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_project_role_template_bindings_list(
            instance_name,
            limit,
            project_id,
            role_template_id,
            user_id,
            user_principal_id,
            group_id,
            group_principal_id,
            namespace_id,
            service_account,
            name,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_project_role_template_binding_get(
    project_role_template_binding_id: str,
    client: ManagementDiscoveryClient,
) -> RancherProjectRoleTemplateBindingDetail:
    """Fetch and normalize one Rancher project role-template binding."""

    payload = await client.get_json(
        f"/v3/projectroletemplatebindings/{project_role_template_binding_id}"
    )
    subject_kind, subject_id = binding_subject(payload)
    return RancherProjectRoleTemplateBindingDetail.model_validate(payload).model_copy(
        update={
            "subject_kind": subject_kind,
            "subject_id": subject_id,
            "link_keys": link_keys(payload),
            "payload": dict(payload),
        }
    )


async def rancher_project_role_template_binding_get(
    project_role_template_binding_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherProjectRoleTemplateBindingDetail:
    """Fetch one Rancher project role-template binding by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_project_role_template_binding_get(
            project_role_template_binding_id,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_project_role_template_binding_get(
            project_role_template_binding_id,
            managed_client,
        )


async def rancher_project_role_template_bindings_list_tool(
    limit: int | None = None,
    project_id: str | None = None,
    role_template_id: str | None = None,
    user_id: str | None = None,
    user_principal_id: str | None = None,
    group_id: str | None = None,
    group_principal_id: str | None = None,
    namespace_id: str | None = None,
    service_account: str | None = None,
    name: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherProjectRoleTemplateBindingList:
    """Public MCP wrapper for curated project role-template-binding list."""

    return await rancher_project_role_template_bindings_list(
        limit=limit,
        project_id=project_id,
        role_template_id=role_template_id,
        user_id=user_id,
        user_principal_id=user_principal_id,
        group_id=group_id,
        group_principal_id=group_principal_id,
        namespace_id=namespace_id,
        service_account=service_account,
        name=name,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_project_role_template_binding_get_tool(
    project_role_template_binding_id: str,
    instance: str | None = None,
) -> RancherProjectRoleTemplateBindingDetail:
    """Public MCP wrapper for curated project role-template-binding detail."""

    return await rancher_project_role_template_binding_get(
        project_role_template_binding_id=project_role_template_binding_id,
        instance=instance,
    )
