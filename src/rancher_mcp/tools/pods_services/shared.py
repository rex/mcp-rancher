# pyright: reportUnusedFunction=false
"""Shared normalization helpers for curated pod and service tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.pods_services import (
    RancherPodContainerSummary,
    RancherPodSummary,
    RancherServicePortSummary,
    RancherServiceSummary,
)
from rancher_mcp.tools._support.collections import object_items
from rancher_mcp.tools._support.conditions import (
    condition_is_true as _condition_is_true,
)
from rancher_mcp.tools._support.conditions import (
    conditions_from_payload as _conditions_from_status,
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
    scalar_to_string as _scalar_to_string,
)
from rancher_mcp.tools._support.values import (
    string_dict as _string_dict,
)
from rancher_mcp.tools._support.values import (
    string_list as _string_list,
)
from rancher_mcp.tools._support.values import (
    string_value as _string_value,
)

__all__ = [
    "_conditions_from_status",
    "_container_summaries",
    "_data_items",
    "_mapping_value",
    "_pod_summary_from_payload",
    "_relationship_types",
    "_service_summary_from_payload",
    "_string_list",
    "_string_value",
]


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

    return object_items(payload, field="data")


def _container_summaries(status: Mapping[str, object]) -> list[RancherPodContainerSummary]:
    """Normalize pod container statuses."""

    raw_statuses = status.get("containerStatuses")
    if not isinstance(raw_statuses, list):
        return []
    containers: list[RancherPodContainerSummary] = []
    for raw_status in cast(list[object], raw_statuses):
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
    for raw_port in cast(list[object], value):
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
    first_owner = cast(list[object], raw_owners)[0]
    if not isinstance(first_owner, dict):
        return None
    return cast(dict[str, object], first_owner)


def _relationship_types(metadata: Mapping[str, object]) -> list[str]:
    """Return sorted relationship targets from service metadata."""

    relationship_values: set[str] = set()
    for relationship in object_items(metadata, field="relationships"):
        to_type = _string_value(relationship, "toType")
        if to_type is not None:
            relationship_values.add(to_type)
        rel = _string_value(relationship, "rel")
        if rel is not None:
            relationship_values.add(rel)
    return sorted(relationship_values)


def _container_state_name(state: Mapping[str, object] | None) -> str | None:
    """Return the first state key present on a container state payload."""

    if state is None:
        return None
    for candidate in ("running", "waiting", "terminated"):
        if _mapping_value(state, candidate) is not None:
            return candidate
    return None
