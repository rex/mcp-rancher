# pyright: reportPrivateUsage=false
"""Curated Rancher cluster tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.clusters_nodes import RancherClusterDetail, RancherClusterList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.clusters_nodes.shared import (
    _build_cluster_query_params,
    _cluster_summary_from_payload,
    _component_statuses_from_payload,
    _conditions_from_payload,
    _data_items,
    _mapping_value,
    _string_value,
)


async def _fetch_clusters_list(
    instance_name: str,
    limit: int | None,
    state: str | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherClusterList:
    """Fetch and normalize the Rancher clusters collection."""

    query_params = _build_cluster_query_params(
        limit=limit,
        state=state,
        sort_by=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/clusters", params=query_params or None)
    clusters = [_cluster_summary_from_payload(item) for item in _data_items(payload)]
    return RancherClusterList(
        instance=instance_name,
        cluster_count=len(clusters),
        applied_query_params=query_params,
        clusters=clusters,
    )


async def rancher_clusters_list(
    limit: int | None = None,
    state: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherClusterList:
    """List Rancher clusters with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_clusters_list(instance_name, limit, state, sort_by, reverse, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_clusters_list(
            instance_name,
            limit,
            state,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_cluster_get(
    instance_name: str,
    cluster_id: str,
    client: ManagementDiscoveryClient,
) -> RancherClusterDetail:
    """Fetch and normalize one Rancher cluster."""

    payload = await client.get_json(f"/v3/clusters/{cluster_id}")
    summary = _cluster_summary_from_payload(payload)
    return RancherClusterDetail(
        id=summary.id,
        name=summary.name,
        display_name=summary.display_name,
        state=summary.state,
        ready=summary.ready,
        provider=summary.provider,
        driver=summary.driver,
        kubernetes_version=summary.kubernetes_version,
        node_count=summary.node_count,
        cpu_capacity=summary.cpu_capacity,
        memory_capacity=summary.memory_capacity,
        condition_types_true=summary.condition_types_true,
        api_endpoint=_string_value(payload, "apiEndpoint"),
        action_keys=sorted(_mapping_value(payload, "actions") or {}),
        conditions=_conditions_from_payload(payload),
        component_statuses=_component_statuses_from_payload(payload),
        payload=dict(payload),
    )


async def rancher_cluster_get(
    cluster_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherClusterDetail:
    """Fetch one Rancher cluster by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cluster_get(instance_name, cluster_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cluster_get(instance_name, cluster_id, managed_client)


async def rancher_clusters_list_tool(
    limit: int | None = None,
    state: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherClusterList:
    """Public MCP wrapper for curated clusters list."""

    return await rancher_clusters_list(
        limit=limit,
        state=state,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_cluster_get_tool(
    cluster_id: str,
    instance: str | None = None,
) -> RancherClusterDetail:
    """Public MCP wrapper for curated cluster detail."""

    return await rancher_cluster_get(cluster_id=cluster_id, instance=instance)
