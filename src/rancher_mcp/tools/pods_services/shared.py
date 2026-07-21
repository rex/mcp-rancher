"""Shared normalization helpers for curated pod and service tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.pods_services import (
    RancherPodContainerSummary,
    RancherPodSummary,
    RancherServiceSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.conditions import (
    condition_is_true as _condition_is_true,
)
from rancher_mcp.tools.support.conditions import (
    conditions_from_payload as _conditions_from_status,
)
from rancher_mcp.tools.support.values import (
    mapping_value as _mapping_value,
)
from rancher_mcp.tools.support.values import (
    string_list as _string_list,
)


def _pod_ready_from_status(status: Mapping[str, object]) -> bool | None:
    """Derive a pod's Ready condition from its raw ``status`` mapping.

    Shared by :func:`_pod_summary_from_payload` and the namespace/project
    rollups (``tools/ops/rollups.py``, M-A4) so both derive "is this pod
    ready" the same way, without either needing the full container-status
    parse that only the pod-detail surfaces require.
    """

    return _condition_is_true(_conditions_from_status(status), "Ready")


def _pod_summary_from_payload(payload: Mapping[str, object]) -> RancherPodSummary:
    """Normalize one pod payload."""

    summary = RancherPodSummary.model_validate(payload)
    status = _mapping_value(payload, "status") or {}
    containers = _container_summaries(status)
    return summary.model_copy(
        update={
            "ready": _pod_ready_from_status(status),
            "ready_containers": sum(1 for container in containers if container.ready is True),
            "total_containers": len(containers),
            "restart_count": sum(container.restart_count or 0 for container in containers),
        }
    )


def _service_summary_from_payload(payload: Mapping[str, object]) -> RancherServiceSummary:
    """Normalize one service payload."""

    return RancherServiceSummary.model_validate(payload)


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher list payload."""

    return object_items(payload, field="data")


def _container_summaries(status: Mapping[str, object]) -> list[RancherPodContainerSummary]:
    """Normalize pod container statuses."""

    raw_statuses = status.get("containerStatuses")
    if not isinstance(raw_statuses, list):
        return []
    return [
        RancherPodContainerSummary.model_validate(raw_status)
        for raw_status in cast(list[object], raw_statuses)
        if isinstance(raw_status, dict)
    ]


def _relationship_types(metadata: Mapping[str, object]) -> list[str]:
    """Return sorted relationship targets from service metadata."""

    relationship_values: set[str] = set()
    for relationship in object_items(metadata, field="relationships"):
        to_type = relationship.get("toType")
        if to_type is not None:
            relationship_values.add(str(to_type))
        rel = relationship.get("rel")
        if rel is not None:
            relationship_values.add(str(rel))
    return sorted(relationship_values)


conditions_from_status = _conditions_from_status
container_summaries = _container_summaries
data_items = _data_items
mapping_value = _mapping_value
pod_ready_from_status = _pod_ready_from_status
pod_summary_from_payload = _pod_summary_from_payload
relationship_types = _relationship_types
service_summary_from_payload = _service_summary_from_payload
string_list = _string_list
