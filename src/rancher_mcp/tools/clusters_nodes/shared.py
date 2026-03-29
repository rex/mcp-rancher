# pyright: reportUnusedFunction=false
"""Shared normalization helpers for curated cluster and node tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.clusters_nodes import (
    RancherClusterComponentStatus,
    RancherClusterSummary,
    RancherCondition,
    RancherNodeSummary,
)
from rancher_mcp.tools._support.collections import object_items
from rancher_mcp.tools._support.conditions import (
    condition_is_true,
    condition_types_true,
    conditions_from_payload,
)
from rancher_mcp.tools._support.conditions import (
    conditions_from_value as _conditions_from_value,
)
from rancher_mcp.tools._support.values import (
    bool_value as _bool_value,
)
from rancher_mcp.tools._support.values import (
    int_value as _int_value,
)
from rancher_mcp.tools._support.values import (
    mapping_value as _mapping_value,
)
from rancher_mcp.tools._support.values import (
    status_to_bool as _status_to_bool,
)
from rancher_mcp.tools._support.values import (
    string_value as _string_value,
)


def _conditions_from_payload(payload: Mapping[str, object]) -> list[RancherCondition]:
    """Normalize top-level conditions from a Rancher payload."""

    return conditions_from_payload(payload)


def _condition_types_true(payload: Mapping[str, object]) -> list[str]:
    """Return sorted condition types whose status is true."""

    return condition_types_true(_conditions_from_payload(payload))


def _condition_is_true(payload: Mapping[str, object], condition_type: str) -> bool | None:
    """Return the boolean value of one named condition if present."""

    return condition_is_true(_conditions_from_payload(payload), condition_type)


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
        condition_types_true=_condition_types_true(payload),
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

    statuses: list[RancherClusterComponentStatus] = []
    for typed_status in object_items(payload, field="componentStatuses"):
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

    return object_items(payload, field="data")
