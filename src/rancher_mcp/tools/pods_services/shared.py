# pyright: reportUnusedFunction=false
"""Shared normalization helpers for curated pod and service tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.models.pods_services import (
    RancherPodContainerSummary,
    RancherPodSummary,
    RancherServicePortSummary,
    RancherServiceSummary,
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
    for item in cast(list[object], raw_items):
        if isinstance(item, dict):
            items.append(cast(dict[str, object], item))
    return items


def _conditions_from_status(status: Mapping[str, object]) -> list[RancherCondition]:
    """Normalize pod conditions from a status payload."""

    raw_conditions = status.get("conditions")
    if not isinstance(raw_conditions, list):
        return []
    conditions: list[RancherCondition] = []
    for raw_condition in cast(list[object], raw_conditions):
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

    raw_relationships = metadata.get("relationships")
    if not isinstance(raw_relationships, list):
        return []
    relationship_values: set[str] = set()
    for raw_relationship in cast(list[object], raw_relationships):
        if not isinstance(raw_relationship, dict):
            continue
        relationship = cast(dict[str, object], raw_relationship)
        to_type = _string_value(relationship, "toType")
        if to_type is not None:
            relationship_values.add(to_type)
        rel = _string_value(relationship, "rel")
        if rel is not None:
            relationship_values.add(rel)
    return sorted(relationship_values)


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
    return [item for item in cast(list[object], value) if isinstance(item, str)]


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
