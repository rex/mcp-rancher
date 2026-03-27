"""Curated Rancher pod and service read-only tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mcp.server.fastmcp import FastMCP

from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.models.pods_services import (
    RancherPodContainerSummary,
    RancherPodDetail,
    RancherPodList,
    RancherPodSummary,
    RancherServiceDetail,
    RancherServiceList,
    RancherServicePortSummary,
    RancherServiceSummary,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import build_steve_list_query_params


async def _fetch_pods_list(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    phase: str | None,
    limit: int | None,
    label_selector: str | None,
    field_selector: str | None,
    client: SteveDiscoveryClient,
) -> RancherPodList:
    """Fetch and normalize the pods collection for one namespace."""

    query_params = build_steve_list_query_params(
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
    )
    payload = await client.get_json(f"/pods/{namespace}", params=query_params or None)
    pods = [_pod_summary_from_payload(item) for item in _data_items(payload)]
    if phase is not None:
        pods = [pod for pod in pods if pod.phase == phase]
    return RancherPodList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        pod_count=len(pods),
        applied_query_params=query_params,
        pods=pods,
    )


async def rancher_pods_list(
    namespace: str,
    cluster_id: str = "local",
    phase: str | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> RancherPodList:
    """List pods in one namespace with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_pods_list(
            instance_name,
            cluster_id,
            namespace,
            phase,
            limit,
            label_selector,
            field_selector,
            client,
        )
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as steve_client:
        return await _fetch_pods_list(
            instance_name,
            cluster_id,
            namespace,
            phase,
            limit,
            label_selector,
            field_selector,
            steve_client,
        )


async def _fetch_pod_get(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    pod_name: str,
    client: SteveDiscoveryClient,
) -> RancherPodDetail:
    """Fetch and normalize one pod."""

    payload = await client.get_json(f"/pods/{namespace}/{pod_name}")
    summary = _pod_summary_from_payload(payload)
    status = _mapping_value(payload, "status") or {}
    return RancherPodDetail(
        id=summary.id,
        name=summary.name,
        namespace=summary.namespace,
        phase=summary.phase,
        ready=summary.ready,
        ready_containers=summary.ready_containers,
        total_containers=summary.total_containers,
        restart_count=summary.restart_count,
        pod_ip=summary.pod_ip,
        node_name=summary.node_name,
        qos_class=summary.qos_class,
        owner_kind=summary.owner_kind,
        owner_name=summary.owner_name,
        host_ip=_string_value(status, "hostIP"),
        service_account_name=_string_value(_mapping_value(payload, "spec"), "serviceAccountName"),
        link_keys=sorted(_mapping_value(payload, "links") or {}),
        conditions=_conditions_from_status(status),
        containers=_container_summaries(status),
        payload=dict(payload),
    )


async def rancher_pod_get(
    namespace: str,
    pod_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> RancherPodDetail:
    """Fetch one pod by namespace and name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_pod_get(
            instance_name,
            cluster_id,
            namespace,
            pod_name,
            client,
        )
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as steve_client:
        return await _fetch_pod_get(
            instance_name,
            cluster_id,
            namespace,
            pod_name,
            steve_client,
        )


async def _fetch_services_list(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    limit: int | None,
    label_selector: str | None,
    client: SteveDiscoveryClient,
) -> RancherServiceList:
    """Fetch and normalize the services collection for one namespace."""

    query_params = build_steve_list_query_params(
        limit=limit,
        label_selector=label_selector,
    )
    payload = await client.get_json(f"/services/{namespace}", params=query_params or None)
    services = [_service_summary_from_payload(item) for item in _data_items(payload)]
    return RancherServiceList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        service_count=len(services),
        applied_query_params=query_params,
        services=services,
    )


async def rancher_services_list(
    namespace: str,
    cluster_id: str = "local",
    limit: int | None = None,
    label_selector: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> RancherServiceList:
    """List services in one namespace with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_services_list(
            instance_name,
            cluster_id,
            namespace,
            limit,
            label_selector,
            client,
        )
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as steve_client:
        return await _fetch_services_list(
            instance_name,
            cluster_id,
            namespace,
            limit,
            label_selector,
            steve_client,
        )


async def _fetch_service_get(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    service_name: str,
    client: SteveDiscoveryClient,
) -> RancherServiceDetail:
    """Fetch and normalize one service."""

    payload = await client.get_json(f"/services/{namespace}/{service_name}")
    summary = _service_summary_from_payload(payload)
    spec = _mapping_value(payload, "spec") or {}
    metadata = _mapping_value(payload, "metadata") or {}
    relationships = _relationship_types(metadata)
    return RancherServiceDetail(
        id=summary.id,
        name=summary.name,
        namespace=summary.namespace,
        service_type=summary.service_type,
        cluster_ip=summary.cluster_ip,
        state_name=summary.state_name,
        state_message=summary.state_message,
        selector=summary.selector,
        ports=summary.ports,
        session_affinity=_string_value(spec, "sessionAffinity"),
        internal_traffic_policy=_string_value(spec, "internalTrafficPolicy"),
        external_ips=_string_list(spec.get("externalIPs")),
        relationship_types=relationships,
        link_keys=sorted(_mapping_value(payload, "links") or {}),
        payload=dict(payload),
    )


async def rancher_service_get(
    namespace: str,
    service_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> RancherServiceDetail:
    """Fetch one service by namespace and name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_service_get(
            instance_name,
            cluster_id,
            namespace,
            service_name,
            client,
        )
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as steve_client:
        return await _fetch_service_get(
            instance_name,
            cluster_id,
            namespace,
            service_name,
            steve_client,
        )


def register_pod_service_tools(mcp: FastMCP) -> None:
    """Register curated pod/service tools with the FastMCP server."""

    mcp.tool(name="rancher_pods_list")(rancher_pods_list_tool)
    mcp.tool(name="rancher_pod_get")(rancher_pod_get_tool)
    mcp.tool(name="rancher_services_list")(rancher_services_list_tool)
    mcp.tool(name="rancher_service_get")(rancher_service_get_tool)


async def rancher_pods_list_tool(
    namespace: str,
    cluster_id: str = "local",
    phase: str | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
) -> RancherPodList:
    """Public MCP wrapper for curated pod list."""

    return await rancher_pods_list(
        namespace=namespace,
        cluster_id=cluster_id,
        phase=phase,
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
        instance=instance,
    )


async def rancher_pod_get_tool(
    namespace: str,
    pod_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherPodDetail:
    """Public MCP wrapper for curated pod detail."""

    return await rancher_pod_get(
        namespace=namespace,
        pod_name=pod_name,
        cluster_id=cluster_id,
        instance=instance,
    )


async def rancher_services_list_tool(
    namespace: str,
    cluster_id: str = "local",
    limit: int | None = None,
    label_selector: str | None = None,
    instance: str | None = None,
) -> RancherServiceList:
    """Public MCP wrapper for curated service list."""

    return await rancher_services_list(
        namespace=namespace,
        cluster_id=cluster_id,
        limit=limit,
        label_selector=label_selector,
        instance=instance,
    )


async def rancher_service_get_tool(
    namespace: str,
    service_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherServiceDetail:
    """Public MCP wrapper for curated service detail."""

    return await rancher_service_get(
        namespace=namespace,
        service_name=service_name,
        cluster_id=cluster_id,
        instance=instance,
    )


def _pod_summary_from_payload(payload: Mapping[str, object]) -> RancherPodSummary:
    """Normalize one pod payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    status = _mapping_value(payload, "status") or {}
    conditions = _conditions_from_status(status)
    containers = _container_summaries(status)
    owner = _first_owner_reference(metadata)
    return RancherPodSummary(
        id=_string_value(payload, "id") or _string_value(metadata, "name") or "<unknown-pod>",
        name=_string_value(metadata, "name") or "<unknown-pod>",
        namespace=_string_value(metadata, "namespace") or "<unknown-namespace>",
        phase=_string_value(status, "phase"),
        ready=_condition_is_true(conditions, "Ready"),
        ready_containers=sum(1 for container in containers if container.ready is True),
        total_containers=len(containers),
        restart_count=sum(container.restart_count or 0 for container in containers),
        pod_ip=_string_value(status, "podIP"),
        node_name=_string_value(_mapping_value(payload, "spec"), "nodeName"),
        qos_class=_string_value(status, "qosClass"),
        owner_kind=_string_value(owner, "kind"),
        owner_name=_string_value(owner, "name"),
    )


def _service_summary_from_payload(payload: Mapping[str, object]) -> RancherServiceSummary:
    """Normalize one service payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    spec = _mapping_value(payload, "spec") or {}
    state = _mapping_value(metadata, "state") or {}
    return RancherServiceSummary(
        id=_string_value(payload, "id") or _string_value(metadata, "name") or "<unknown-service>",
        name=_string_value(metadata, "name") or "<unknown-service>",
        namespace=_string_value(metadata, "namespace") or "<unknown-namespace>",
        service_type=_string_value(spec, "type"),
        cluster_ip=_string_value(spec, "clusterIP"),
        state_name=_string_value(state, "name"),
        state_message=_string_value(state, "message"),
        selector=_string_dict(spec.get("selector")),
        ports=_service_ports(spec.get("ports")),
    )


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


def _conditions_from_status(status: Mapping[str, object]) -> list[RancherCondition]:
    """Normalize pod conditions from a status payload."""

    raw_conditions = status.get("conditions")
    if not isinstance(raw_conditions, list):
        return []
    conditions: list[RancherCondition] = []
    typed_conditions = cast(list[object], raw_conditions)
    for raw_condition in typed_conditions:
        if not isinstance(raw_condition, dict):
            continue
        condition = cast(dict[str, object], raw_condition)
        condition_type = _string_value(condition, "type")
        if condition_type is None:
            continue
        conditions.append(
            RancherCondition(
                type=condition_type,
                status=_string_value(condition, "status"),
                reason=_string_value(condition, "reason"),
                message=_string_value(condition, "message"),
            )
        )
    return conditions


def _container_summaries(status: Mapping[str, object]) -> list[RancherPodContainerSummary]:
    """Normalize pod container statuses."""

    raw_statuses = status.get("containerStatuses")
    if not isinstance(raw_statuses, list):
        return []
    containers: list[RancherPodContainerSummary] = []
    typed_statuses = cast(list[object], raw_statuses)
    for raw_status in typed_statuses:
        if not isinstance(raw_status, dict):
            continue
        container = cast(dict[str, object], raw_status)
        containers.append(
            RancherPodContainerSummary(
                name=_string_value(container, "name") or "<unknown-container>",
                image=_string_value(container, "image"),
                ready=_bool_value(container, "ready"),
                restart_count=_int_value(container, "restartCount"),
                state=_container_state_name(_mapping_value(container, "state")),
            )
        )
    return containers


def _service_ports(value: object) -> list[RancherServicePortSummary]:
    """Normalize service ports."""

    if not isinstance(value, list):
        return []
    ports: list[RancherServicePortSummary] = []
    typed_ports = cast(list[object], value)
    for raw_port in typed_ports:
        if not isinstance(raw_port, dict):
            continue
        port = cast(dict[str, object], raw_port)
        ports.append(
            RancherServicePortSummary(
                name=_string_value(port, "name"),
                protocol=_string_value(port, "protocol"),
                port=_int_value(port, "port"),
                target_port=_scalar_to_string(port.get("targetPort")),
            )
        )
    return ports


def _first_owner_reference(metadata: Mapping[str, object]) -> dict[str, object] | None:
    """Return the first owner reference if present."""

    raw_owners = metadata.get("ownerReferences")
    if not isinstance(raw_owners, list) or not raw_owners:
        return None
    typed_owners = cast(list[object], raw_owners)
    first_owner = typed_owners[0]
    if not isinstance(first_owner, dict):
        return None
    return cast(dict[str, object], first_owner)


def _relationship_types(metadata: Mapping[str, object]) -> list[str]:
    """Return sorted relationship targets from service metadata."""

    raw_relationships = metadata.get("relationships")
    if not isinstance(raw_relationships, list):
        return []
    relationship_types: set[str] = set()
    typed_relationships = cast(list[object], raw_relationships)
    for raw_relationship in typed_relationships:
        if not isinstance(raw_relationship, dict):
            continue
        relationship = cast(dict[str, object], raw_relationship)
        to_type = _string_value(relationship, "toType")
        if to_type is not None:
            relationship_types.add(to_type)
        rel = _string_value(relationship, "rel")
        if rel is not None:
            relationship_types.add(rel)
    return sorted(relationship_types)


def _condition_is_true(conditions: list[RancherCondition], condition_type: str) -> bool | None:
    """Return the boolean value of one named condition if present."""

    for condition in conditions:
        if condition.type == condition_type:
            return _status_to_bool(condition.status)
    return None


def _container_state_name(state: Mapping[str, object] | None) -> str | None:
    """Return the first state key present on a container state payload."""

    if state is None:
        return None
    for candidate in ("running", "waiting", "terminated"):
        if isinstance(state.get(candidate), dict):
            return candidate
    return None


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


def _string_dict(value: object) -> dict[str, str]:
    """Normalize an arbitrary value into a string-to-string mapping."""

    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, raw_value in cast(dict[object, object], value).items():
        if isinstance(key, str) and isinstance(raw_value, str):
            result[key] = raw_value
    return result


def _string_list(value: object) -> list[str]:
    """Normalize an arbitrary value into a list of strings."""

    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in cast(list[object], value):
        if isinstance(item, str):
            result.append(item)
    return result


def _scalar_to_string(value: object) -> str | None:
    """Normalize a scalar service targetPort value to a string."""

    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    return None


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
