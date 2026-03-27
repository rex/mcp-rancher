"""Curated Rancher cluster and node read-only tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mcp.server.fastmcp import FastMCP

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.clusters_nodes import (
    RancherClusterComponentStatus,
    RancherClusterDetail,
    RancherClusterList,
    RancherClusterSummary,
    RancherCondition,
    RancherNodeDetail,
    RancherNodeList,
    RancherNodeSummary,
)
from rancher_mcp.services.instances import resolve_instance


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
        return await _fetch_clusters_list(
            instance_name,
            limit,
            state,
            sort_by,
            reverse,
            client,
        )
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


def register_cluster_node_tools(mcp: FastMCP) -> None:
    """Register curated cluster/node tools with the FastMCP server."""

    mcp.tool(name="rancher_clusters_list")(rancher_clusters_list_tool)
    mcp.tool(name="rancher_cluster_get")(rancher_cluster_get_tool)
    mcp.tool(name="rancher_nodes_list")(rancher_nodes_list_tool)
    mcp.tool(name="rancher_node_get")(rancher_node_get_tool)


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

    return await rancher_cluster_get(
        cluster_id=cluster_id,
        instance=instance,
    )


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

    return await rancher_node_get(
        node_id=node_id,
        instance=instance,
    )


def _build_cluster_query_params(
    *,
    limit: int | None,
    state: str | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher clusters collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if state is not None:
        params["state"] = state
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_node_query_params(
    *,
    cluster_id: str | None,
    state: str | None,
    role: str | None,
    unschedulable: bool | None,
    limit: int | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher nodes collection."""

    params: dict[str, str | int | bool] = {}
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if state is not None:
        params["state"] = state
    if role == "control-plane":
        params["controlPlane"] = True
    elif role == "etcd":
        params["etcd"] = True
    elif role == "worker":
        params["worker"] = True
    if unschedulable is not None:
        params["unschedulable"] = unschedulable
    if limit is not None:
        params["limit"] = limit
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _cluster_summary_from_payload(payload: Mapping[str, object]) -> RancherClusterSummary:
    """Normalize one Rancher cluster payload."""

    cluster_id = _string_value(payload, "id")
    display_name = _string_value(payload, "displayName")
    name = _string_value(payload, "name")
    capacity = _mapping_value(payload, "capacity") or {}
    condition_types_true = _condition_types_true(payload)
    return RancherClusterSummary(
        id=cluster_id or name or "<unknown-cluster>",
        name=name or cluster_id or "<unknown-cluster>",
        display_name=display_name,
        state=_string_value(payload, "state"),
        ready=_condition_is_true(payload, "Ready"),
        provider=_string_value(payload, "provider"),
        driver=_string_value(payload, "driver"),
        kubernetes_version=_cluster_kubernetes_version(payload),
        node_count=_int_value(payload, "nodeCount"),
        cpu_capacity=_string_value(capacity, "cpu"),
        memory_capacity=_string_value(capacity, "memory"),
        condition_types_true=condition_types_true,
    )


def _node_summary_from_payload(payload: Mapping[str, object]) -> RancherNodeSummary:
    """Normalize one Rancher node payload."""

    node_id = _string_value(payload, "id")
    name = _string_value(payload, "name")
    info = _mapping_value(payload, "info") or {}
    kubernetes = _mapping_value(info, "kubernetes") or {}
    return RancherNodeSummary(
        id=node_id or name or "<unknown-node>",
        name=name or node_id or "<unknown-node>",
        cluster_id=_string_value(payload, "clusterId"),
        hostname=_string_value(payload, "hostname"),
        state=_string_value(payload, "state"),
        ready=_condition_is_true(payload, "Ready"),
        roles=_node_roles(payload),
        kubernetes_version=_string_value(kubernetes, "kubeletVersion"),
        internal_ip=_string_value(payload, "ipAddress"),
        external_ip=_string_value(payload, "externalIpAddress"),
        unschedulable=_bool_value(payload, "unschedulable"),
    )


def _cluster_kubernetes_version(payload: Mapping[str, object]) -> str | None:
    """Read the most trustworthy Kubernetes version field from a cluster payload."""

    raw_node_version = payload.get("nodeVersion")
    if isinstance(raw_node_version, str) and raw_node_version:
        return raw_node_version
    version = _mapping_value(payload, "version")
    return _string_value(version, "gitVersion")


def _component_statuses_from_payload(
    payload: Mapping[str, object],
) -> list[RancherClusterComponentStatus]:
    """Normalize cluster component statuses."""

    raw_statuses = payload.get("componentStatuses")
    if not isinstance(raw_statuses, list):
        return []
    statuses: list[RancherClusterComponentStatus] = []
    typed_statuses = cast(list[object], raw_statuses)
    for raw_status in typed_statuses:
        if not isinstance(raw_status, dict):
            continue
        typed_status = cast(dict[str, object], raw_status)
        conditions = _conditions_from_value(typed_status.get("conditions"))
        healthy_condition = next((item for item in conditions if item.type == "Healthy"), None)
        statuses.append(
            RancherClusterComponentStatus(
                name=_string_value(typed_status, "name") or "<unknown-component>",
                healthy=_status_to_bool(healthy_condition.status) if healthy_condition else None,
                message=healthy_condition.message if healthy_condition else None,
            )
        )
    return statuses


def _conditions_from_payload(payload: Mapping[str, object]) -> list[RancherCondition]:
    """Normalize top-level conditions from a Rancher payload."""

    return _conditions_from_value(payload.get("conditions"))


def _conditions_from_value(value: object) -> list[RancherCondition]:
    """Normalize an arbitrary condition list."""

    if not isinstance(value, list):
        return []
    conditions: list[RancherCondition] = []
    typed_values = cast(list[object], value)
    for item in typed_values:
        if not isinstance(item, dict):
            continue
        typed_item = cast(dict[str, object], item)
        condition_type = _string_value(typed_item, "type")
        if condition_type is None:
            continue
        conditions.append(
            RancherCondition(
                type=condition_type,
                status=_string_value(typed_item, "status"),
                reason=_string_value(typed_item, "reason"),
                message=_string_value(typed_item, "message"),
            )
        )
    return conditions


def _condition_types_true(payload: Mapping[str, object]) -> list[str]:
    """Return sorted condition types whose status is true."""

    return sorted(
        condition.type
        for condition in _conditions_from_payload(payload)
        if _status_to_bool(condition.status) is True
    )


def _condition_is_true(payload: Mapping[str, object], condition_type: str) -> bool | None:
    """Return the boolean value of one named condition if present."""

    for condition in _conditions_from_payload(payload):
        if condition.type == condition_type:
            return _status_to_bool(condition.status)
    return None


def _node_roles(payload: Mapping[str, object]) -> list[str]:
    """Return normalized Rancher node roles."""

    roles: list[str] = []
    if _bool_value(payload, "controlPlane") is True:
        roles.append("control-plane")
    if _bool_value(payload, "etcd") is True:
        roles.append("etcd")
    if _bool_value(payload, "worker") is True:
        roles.append("worker")
    return roles


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher list payload."""

    raw_items = payload.get("data")
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, object]] = []
    typed_items = cast(list[object], raw_items)
    for item in typed_items:
        if isinstance(item, dict):
            items.append(cast(dict[str, object], item))
    return items


def _mapping_value(
    payload: Mapping[str, object] | None,
    key: str,
) -> dict[str, object] | None:
    """Read one nested mapping value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    if not isinstance(raw_value, dict):
        return None
    return cast(dict[str, object], raw_value)


def _string_value(payload: Mapping[str, object] | None, key: str) -> str | None:
    """Read one string value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, str) else None


def _int_value(payload: Mapping[str, object] | None, key: str) -> int | None:
    """Read one integer value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, int) else None


def _bool_value(payload: Mapping[str, object] | None, key: str) -> bool | None:
    """Read one boolean value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, bool) else None


def _status_to_bool(status: str | None) -> bool | None:
    """Normalize Rancher condition status strings to booleans."""

    if status is None:
        return None
    lowered = status.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None
