"""Curated Rancher cluster-logging tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.logging_backups import (
    RancherClusterLoggingDetail,
    RancherClusterLoggingList,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.logging_backups.shared import (
    action_keys,
    build_query_params,
    cluster_logging_summary_from_payload,
    data_items,
    link_keys,
    target_types,
)
from rancher_mcp.tools.support.values import mapping_value


async def _fetch_cluster_loggings_list(
    instance_name: str,
    limit: int | None,
    cluster_id: str | None,
    name: str | None,
    state: str | None,
    enable_json_parsing: bool | None,
    include_system_component: bool | None,
    output_flush_interval: int | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherClusterLoggingList:
    """Fetch and normalize the Rancher cluster-logging collection."""

    query_params = build_query_params(
        limit=limit,
        clusterId=cluster_id,
        name=name,
        state=state,
        enableJSONParsing=enable_json_parsing,
        includeSystemComponent=include_system_component,
        outputFlushInterval=output_flush_interval,
        sort=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/clusterloggings", params=query_params or None)
    cluster_loggings = [cluster_logging_summary_from_payload(item) for item in data_items(payload)]
    return RancherClusterLoggingList(
        instance=instance_name,
        cluster_logging_count=len(cluster_loggings),
        applied_query_params=query_params,
        cluster_loggings=cluster_loggings,
    )


async def rancher_cluster_loggings_list(
    limit: int | None = None,
    cluster_id: str | None = None,
    name: str | None = None,
    state: str | None = None,
    enable_json_parsing: bool | None = None,
    include_system_component: bool | None = None,
    output_flush_interval: int | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherClusterLoggingList:
    """List Rancher cluster logging resources with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cluster_loggings_list(
            instance_name,
            limit,
            cluster_id,
            name,
            state,
            enable_json_parsing,
            include_system_component,
            output_flush_interval,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cluster_loggings_list(
            instance_name,
            limit,
            cluster_id,
            name,
            state,
            enable_json_parsing,
            include_system_component,
            output_flush_interval,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_cluster_logging_get(
    cluster_logging_id: str,
    client: ManagementDiscoveryClient,
) -> RancherClusterLoggingDetail:
    """Fetch and normalize one Rancher cluster logging resource."""

    payload = await client.get_json(f"/v3/clusterloggings/{cluster_logging_id}")
    return RancherClusterLoggingDetail.model_validate(payload).model_copy(
        update={
            "status": mapping_value(payload, "status") or {},
            "status_keys": sorted((mapping_value(payload, "status") or {}).keys()),
            "target_types": target_types(payload),
            "action_keys": action_keys(payload),
            "link_keys": link_keys(payload),
            "payload": dict(payload),
        }
    )


async def rancher_cluster_logging_get(
    cluster_logging_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherClusterLoggingDetail:
    """Fetch one Rancher cluster logging resource by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cluster_logging_get(cluster_logging_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cluster_logging_get(cluster_logging_id, managed_client)


async def rancher_cluster_loggings_list_tool(
    limit: int | None = None,
    cluster_id: str | None = None,
    name: str | None = None,
    state: str | None = None,
    enable_json_parsing: bool | None = None,
    include_system_component: bool | None = None,
    output_flush_interval: int | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherClusterLoggingList:
    """Public MCP wrapper for curated cluster-logging list."""

    return await rancher_cluster_loggings_list(
        limit=limit,
        cluster_id=cluster_id,
        name=name,
        state=state,
        enable_json_parsing=enable_json_parsing,
        include_system_component=include_system_component,
        output_flush_interval=output_flush_interval,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_cluster_logging_get_tool(
    cluster_logging_id: str,
    instance: str | None = None,
) -> RancherClusterLoggingDetail:
    """Public MCP wrapper for curated cluster-logging detail."""

    return await rancher_cluster_logging_get(
        cluster_logging_id=cluster_logging_id,
        instance=instance,
    )
