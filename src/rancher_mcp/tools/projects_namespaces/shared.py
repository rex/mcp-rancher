# pyright: reportUnusedFunction=false
"""Shared normalization helpers for curated project and namespace tools."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.models.projects_namespaces import (
    RancherNamespaceSummary,
    RancherProjectSummary,
)
from rancher_mcp.services.resource_queries import build_steve_list_query_params


def _build_project_query_params(
    *,
    cluster_id: str | None,
    state: str | None,
    limit: int | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher projects collection."""

    params: dict[str, str | int | bool] = {}
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if state is not None:
        params["state"] = state
    if limit is not None:
        params["limit"] = limit
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_namespace_query_params(
    *,
    project_id: str | None,
    limit: int | None,
    label_selector: str | None,
    field_selector: str | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the downstream namespaces collection."""

    merged_label_selector = _merge_project_label_selector(label_selector, project_id)
    return build_steve_list_query_params(
        limit=limit,
        label_selector=merged_label_selector,
        field_selector=field_selector,
    )


def _project_summary_from_payload(payload: Mapping[str, object]) -> RancherProjectSummary:
    """Normalize one Rancher project payload."""

    labels = _mapping_value(payload, "labels") or {}
    return RancherProjectSummary(
        id=_string_value(payload, "id") or "<unknown-project>",
        name=_string_value(payload, "name") or "<unknown-project>",
        cluster_id=_string_value(payload, "clusterId"),
        state=_string_value(payload, "state"),
        description=_string_value(payload, "description"),
        monitoring_enabled=_bool_value(payload, "enableProjectMonitoring"),
        default_project=_label_true(labels, "authz.management.cattle.io/default-project"),
        system_project=_label_true(labels, "authz.management.cattle.io/system-project"),
        condition_types_true=_condition_types_true(payload),
    )


def _namespace_summary_from_payload(
    cluster_id: str,
    payload: Mapping[str, object],
) -> RancherNamespaceSummary:
    """Normalize one downstream namespace payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    annotations = _mapping_value(metadata, "annotations") or {}
    labels = _mapping_value(metadata, "labels") or {}
    state = _mapping_value(metadata, "state") or {}
    project_id_short = _string_value(labels, "field.cattle.io/projectId")
    return RancherNamespaceSummary(
        id=_string_value(payload, "id") or _string_value(metadata, "name") or "<unknown-namespace>",
        name=_string_value(metadata, "name") or "<unknown-namespace>",
        cluster_id=cluster_id,
        phase=_string_value(_mapping_value(payload, "status"), "phase"),
        state_name=_string_value(state, "name"),
        state_message=_string_value(state, "message"),
        state_error=_bool_value(state, "error"),
        project_id=_string_value(annotations, "field.cattle.io/projectId") or project_id_short,
        project_id_short=project_id_short,
        finalizer_count=len(_string_list(metadata.get("finalizers"))),
    )


def _conditions_from_payload(payload: Mapping[str, object]) -> list[RancherCondition]:
    """Normalize Rancher conditions from a payload."""

    raw_conditions = payload.get("conditions")
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


def _namespace_cattle_conditions(metadata: Mapping[str, object]) -> list[RancherCondition]:
    """Parse Rancher namespace conditions from the embedded cattle status annotation."""

    annotations = _mapping_value(metadata, "annotations") or {}
    raw_status = _string_value(annotations, "cattle.io/status")
    if raw_status is None:
        return []
    try:
        decoded: object = json.loads(raw_status)
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, dict):
        return []
    raw_conditions = cast(dict[str, object], decoded).get("Conditions")
    if not isinstance(raw_conditions, list):
        return []
    conditions: list[RancherCondition] = []
    for raw_condition in cast(list[object], raw_conditions):
        if not isinstance(raw_condition, dict):
            continue
        condition = cast(dict[str, object], raw_condition)
        condition_type = _string_value(condition, "Type")
        if condition_type is None:
            continue
        conditions.append(
            RancherCondition(
                type=condition_type,
                status=_string_value(condition, "Status"),
                reason=_string_value(condition, "Reason"),
                message=_string_value(condition, "Message"),
            )
        )
    return conditions


def _condition_types_true(payload: Mapping[str, object]) -> list[str]:
    """Return sorted Rancher condition types whose status is true."""

    return sorted(
        condition.type
        for condition in _conditions_from_payload(payload)
        if _status_to_bool(condition.status) is True
    )


def _merge_project_label_selector(
    label_selector: str | None,
    project_id: str | None,
) -> str | None:
    """Merge a namespace project filter into any user-provided label selector."""

    project_selector = _project_label_selector(project_id)
    if project_selector is None:
        return label_selector
    if label_selector is None:
        return project_selector
    return f"{label_selector},{project_selector}"


def _project_label_selector(project_id: str | None) -> str | None:
    """Convert a Rancher project id into the namespace project label selector."""

    if project_id is None:
        return None
    if ":" in project_id:
        _, _, short_project_id = project_id.partition(":")
    else:
        short_project_id = project_id
    if not short_project_id:
        return None
    return f"field.cattle.io/projectId={short_project_id}"


def _label_true(labels: Mapping[str, object], key: str) -> bool | None:
    """Return one label value normalized as a boolean when possible."""

    return _status_to_bool(_string_value(labels, key))


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


def _status_to_bool(status: str | None) -> bool | None:
    """Normalize Rancher condition-style strings to booleans."""

    if status is None:
        return None
    lowered = status.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None
