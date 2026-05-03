"""Curated Rancher project tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.projects_namespaces import RancherProjectDetail, RancherProjectList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resources.builders_pagination import next_page_token_from_payload
from rancher_mcp.tools.projects_namespaces.shared import (
    build_project_query_params,
    data_items,
    project_summary_from_payload,
)
from rancher_mcp.tools.support.values import mapping_value


async def _fetch_projects_list(
    instance_name: str,
    cluster_id: str | None,
    state: str | None,
    limit: int | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
    page_token: str | None = None,
) -> RancherProjectList:
    """Fetch and normalize the Rancher projects collection."""

    query_params = build_project_query_params(
        cluster_id=cluster_id,
        state=state,
        limit=limit,
        sort_by=sort_by,
        reverse=reverse,
        marker=page_token,
    )
    payload = await client.get_json("/v3/projects", params=query_params or None)
    projects = [project_summary_from_payload(item) for item in data_items(payload)]
    return RancherProjectList(
        instance=instance_name,
        project_count=len(projects),
        next_page_token=next_page_token_from_payload(payload),
        applied_query_params=query_params,
        projects=projects,
    )


async def rancher_projects_list(
    cluster_id: str | None = None,
    state: str | None = None,
    limit: int | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    page_token: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherProjectList:
    """List Rancher projects with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_projects_list(
            instance_name,
            cluster_id,
            state,
            limit,
            sort_by,
            reverse,
            client,
            page_token,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_projects_list(
            instance_name,
            cluster_id,
            state,
            limit,
            sort_by,
            reverse,
            managed_client,
            page_token,
        )


async def _fetch_project_get(
    instance_name: str,
    project_id: str,
    client: ManagementDiscoveryClient,
) -> RancherProjectDetail:
    """Fetch and normalize one Rancher project."""

    payload = await client.get_json(f"/v3/projects/{project_id}")
    summary = project_summary_from_payload(payload)
    return RancherProjectDetail.model_validate(payload).model_copy(
        update={
            "default_project": summary.default_project,
            "system_project": summary.system_project,
            "condition_types_true": summary.condition_types_true,
            "action_keys": sorted(mapping_value(payload, "actions") or {}),
            "link_keys": sorted(mapping_value(payload, "links") or {}),
            "payload": dict(payload),
        }
    )


async def rancher_project_get(
    project_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherProjectDetail:
    """Fetch one Rancher project by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_project_get(instance_name, project_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_project_get(instance_name, project_id, managed_client)


async def rancher_projects_list_tool(
    cluster_id: str | None = None,
    state: str | None = None,
    limit: int | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    page_token: str | None = None,
    instance: str | None = None,
) -> RancherProjectList:
    """Public MCP wrapper for curated project list."""

    return await rancher_projects_list(
        cluster_id=cluster_id,
        state=state,
        limit=limit,
        sort_by=sort_by,
        reverse=reverse,
        page_token=page_token,
        instance=instance,
    )


async def rancher_project_get_tool(
    project_id: str,
    instance: str | None = None,
) -> RancherProjectDetail:
    """Public MCP wrapper for curated project detail."""

    return await rancher_project_get(project_id=project_id, instance=instance)
