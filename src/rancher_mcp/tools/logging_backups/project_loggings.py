"""Curated Rancher project-logging tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.logging_backups import (
    RancherProjectLoggingDetail,
    RancherProjectLoggingList,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.logging_backups.shared import (
    action_keys,
    build_query_params,
    data_items,
    link_keys,
    project_logging_summary_from_payload,
    target_types,
)
from rancher_mcp.tools.support.values import mapping_value


async def _fetch_project_loggings_list(
    instance_name: str,
    limit: int | None,
    project_id: str | None,
    name: str | None,
    state: str | None,
    enable_json_parsing: bool | None,
    output_flush_interval: int | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherProjectLoggingList:
    """Fetch and normalize the Rancher project-logging collection."""

    query_params = build_query_params(
        limit=limit,
        projectId=project_id,
        name=name,
        state=state,
        enableJSONParsing=enable_json_parsing,
        outputFlushInterval=output_flush_interval,
        sort=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/projectloggings", params=query_params or None)
    project_loggings = [project_logging_summary_from_payload(item) for item in data_items(payload)]
    return RancherProjectLoggingList(
        instance=instance_name,
        project_logging_count=len(project_loggings),
        applied_query_params=query_params,
        project_loggings=project_loggings,
    )


async def rancher_project_loggings_list(
    limit: int | None = None,
    project_id: str | None = None,
    name: str | None = None,
    state: str | None = None,
    enable_json_parsing: bool | None = None,
    output_flush_interval: int | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherProjectLoggingList:
    """List Rancher project logging resources with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_project_loggings_list(
            instance_name,
            limit,
            project_id,
            name,
            state,
            enable_json_parsing,
            output_flush_interval,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_project_loggings_list(
            instance_name,
            limit,
            project_id,
            name,
            state,
            enable_json_parsing,
            output_flush_interval,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_project_logging_get(
    project_logging_id: str,
    client: ManagementDiscoveryClient,
) -> RancherProjectLoggingDetail:
    """Fetch and normalize one Rancher project logging resource."""

    payload = await client.get_json(f"/v3/projectloggings/{project_logging_id}")
    return RancherProjectLoggingDetail.model_validate(payload).model_copy(
        update={
            "status": mapping_value(payload, "status") or {},
            "status_keys": sorted((mapping_value(payload, "status") or {}).keys()),
            "target_types": target_types(payload),
            "action_keys": action_keys(payload),
            "link_keys": link_keys(payload),
            "payload": dict(payload),
        }
    )


async def rancher_project_logging_get(
    project_logging_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherProjectLoggingDetail:
    """Fetch one Rancher project logging resource by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_project_logging_get(project_logging_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_project_logging_get(project_logging_id, managed_client)


async def rancher_project_loggings_list_tool(
    limit: int | None = None,
    project_id: str | None = None,
    name: str | None = None,
    state: str | None = None,
    enable_json_parsing: bool | None = None,
    output_flush_interval: int | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherProjectLoggingList:
    """Public MCP wrapper for curated project-logging list."""

    return await rancher_project_loggings_list(
        limit=limit,
        project_id=project_id,
        name=name,
        state=state,
        enable_json_parsing=enable_json_parsing,
        output_flush_interval=output_flush_interval,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_project_logging_get_tool(
    project_logging_id: str,
    instance: str | None = None,
) -> RancherProjectLoggingDetail:
    """Public MCP wrapper for curated project-logging detail."""

    return await rancher_project_logging_get(
        project_logging_id=project_logging_id,
        instance=instance,
    )
