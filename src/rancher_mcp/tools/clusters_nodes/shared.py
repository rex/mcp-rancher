"""Shared normalization helpers for curated cluster and node tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.clusters_nodes import (
    RancherClusterComponentStatus,
    RancherClusterSummary,
    RancherCondition,
    RancherNodeSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.conditions import (
    condition_is_true,
    condition_types_true,
)
from rancher_mcp.tools.support.conditions import (
    conditions_from_payload as support_conditions_from_payload,
)
from rancher_mcp.tools.support.values import (
    bool_value as _bool_value,
)


def _conditions_from_payload(payload: Mapping[str, object]) -> list[RancherCondition]:
    """Normalize top-level conditions from a Rancher payload."""

    return support_conditions_from_payload(payload)


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
    marker: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher clusters collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if marker is not None:
        params["marker"] = marker
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
    marker: str | None = None,
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
    if marker is not None:
        params["marker"] = marker
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _cluster_summary_from_payload(payload: Mapping[str, object]) -> RancherClusterSummary:
    """Normalize one Rancher cluster payload."""

    summary = RancherClusterSummary.model_validate(payload)
    return summary.model_copy(
        update={
            "id": summary.id or summary.name or "<unknown-cluster>",
            "name": summary.name or summary.id or "<unknown-cluster>",
            "ready": _condition_is_true(payload, "Ready"),
            "condition_types_true": _condition_types_true(payload),
        }
    )


def _node_summary_from_payload(payload: Mapping[str, object]) -> RancherNodeSummary:
    """Normalize one Rancher node payload."""

    summary = RancherNodeSummary.model_validate(payload)
    return summary.model_copy(
        update={
            "id": summary.id or summary.name or "<unknown-node>",
            "name": summary.name or summary.id or "<unknown-node>",
            "ready": _condition_is_true(payload, "Ready"),
            "roles": _node_roles(payload),
        }
    )


def _component_statuses_from_payload(
    payload: Mapping[str, object],
) -> list[RancherClusterComponentStatus]:
    """Normalize cluster component statuses."""

    return [
        RancherClusterComponentStatus.model_validate(typed_status)
        for typed_status in object_items(payload, field="componentStatuses")
    ]


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


build_cluster_query_params = _build_cluster_query_params
build_node_query_params = _build_node_query_params
cluster_summary_from_payload = _cluster_summary_from_payload
component_statuses_from_payload = _component_statuses_from_payload
conditions_from_payload = _conditions_from_payload
data_items = _data_items
node_summary_from_payload = _node_summary_from_payload
