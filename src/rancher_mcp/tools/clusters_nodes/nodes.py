# pyright: reportPrivateUsage=false
"""Curated Rancher node tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.clusters_nodes import RancherNodeDetail, RancherNodeList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.clusters_nodes.shared import (
    _build_node_query_params,
    _conditions_from_payload,
    _data_items,
    _mapping_value,
    _node_summary_from_payload,
    _string_value,
)


async def _fetch_nodes_list(
    instance_name: str,
    cluster_id: str | None,
    state: str | None,
    role: str | None,
    unschedulable: bool | None,
    limit: int | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherNodeList:
    """Fetch and normalize the Rancher nodes collection."""

    query_params = _build_node_query_params(
        cluster_id=cluster_id,
        state=state,
        role=role,
        unschedulable=unschedulable,
        limit=limit,
        sort_by=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/nodes", params=query_params or None)
    nodes = [_node_summary_from_payload(item) for item in _data_items(payload)]
    return RancherNodeList(
        instance=instance_name,
        node_count=len(nodes),
        applied_query_params=query_params,
        nodes=nodes,
    )


async def rancher_nodes_list(
    cluster_id: str | None = None,
    state: str | None = None,
    role: str | None = None,
    unschedulable: bool | None = None,
    limit: int | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherNodeList:
    """List Rancher nodes with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_nodes_list(
            instance_name,
            cluster_id,
            state,
            role,
            unschedulable,
            limit,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_nodes_list(
            instance_name,
            cluster_id,
            state,
            role,
            unschedulable,
            limit,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_node_get(
    instance_name: str,
    node_id: str,
    client: ManagementDiscoveryClient,
) -> RancherNodeDetail:
    """Fetch and normalize one Rancher node."""

    payload = await client.get_json(f"/v3/nodes/{node_id}")
    summary = _node_summary_from_payload(payload)
    allocatable = _mapping_value(payload, "allocatable") or {}
    capacity = _mapping_value(payload, "capacity") or {}
    return RancherNodeDetail(
        id=summary.id,
        name=summary.name,
        cluster_id=summary.cluster_id,
        hostname=summary.hostname,
        state=summary.state,
        ready=summary.ready,
        roles=summary.roles,
        kubernetes_version=summary.kubernetes_version,
        internal_ip=summary.internal_ip,
        external_ip=summary.external_ip,
        unschedulable=summary.unschedulable,
        node_name=_string_value(payload, "nodeName"),
        provider_id=_string_value(payload, "providerId"),
        pod_cidr=_string_value(payload, "podCidr"),
        cpu_capacity=_string_value(capacity, "cpu"),
        memory_capacity=_string_value(capacity, "memory"),
        pod_capacity=_string_value(capacity, "pods"),
        cpu_allocatable=_string_value(allocatable, "cpu"),
        memory_allocatable=_string_value(allocatable, "memory"),
        pod_allocatable=_string_value(allocatable, "pods"),
        action_keys=sorted(_mapping_value(payload, "actions") or {}),
        conditions=_conditions_from_payload(payload),
        payload=dict(payload),
    )


async def rancher_node_get(
    node_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherNodeDetail:
    """Fetch one Rancher node by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_node_get(instance_name, node_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_node_get(instance_name, node_id, managed_client)


async def rancher_nodes_list_tool(
    cluster_id: str | None = None,
    state: str | None = None,
    role: str | None = None,
    unschedulable: bool | None = None,
    limit: int | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherNodeList:
    """Public MCP wrapper for curated nodes list."""

    return await rancher_nodes_list(
        cluster_id=cluster_id,
        state=state,
        role=role,
        unschedulable=unschedulable,
        limit=limit,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_node_get_tool(
    node_id: str,
    instance: str | None = None,
) -> RancherNodeDetail:
    """Public MCP wrapper for curated node detail."""

    return await rancher_node_get(node_id=node_id, instance=instance)
