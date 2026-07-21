"""Shared condition-normalization helpers for curated tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.tools.support.values import status_to_bool, string_value


def conditions_from_value(
    value: object,
    *,
    type_key: str = "type",
    status_key: str = "status",
    reason_key: str = "reason",
    message_key: str = "message",
) -> list[RancherCondition]:
    """Normalize an arbitrary condition list into typed Rancher conditions."""

    if not isinstance(value, list):
        return []

    conditions: list[RancherCondition] = []
    for item in cast(list[object], value):
        if not isinstance(item, dict):
            continue
        typed_item = cast(dict[str, object], item)
        condition_type = string_value(typed_item, type_key)
        if condition_type is None:
            continue
        conditions.append(
            RancherCondition(
                type=condition_type,
                status=string_value(typed_item, status_key),
                reason=string_value(typed_item, reason_key),
                message=string_value(typed_item, message_key),
                last_transition_time=string_value(typed_item, "lastTransitionTime"),
            )
        )
    return conditions


def conditions_from_payload(
    payload: Mapping[str, object],
    *,
    field: str = "conditions",
    type_key: str = "type",
    status_key: str = "status",
    reason_key: str = "reason",
    message_key: str = "message",
) -> list[RancherCondition]:
    """Read one condition field from a payload and normalize it."""

    return conditions_from_value(
        payload.get(field),
        type_key=type_key,
        status_key=status_key,
        reason_key=reason_key,
        message_key=message_key,
    )


def condition_is_true(
    conditions: list[RancherCondition],
    condition_type: str,
) -> bool | None:
    """Return one named condition as a boolean when present."""

    for condition in conditions:
        if condition.type == condition_type:
            return status_to_bool(condition.status)
    return None


def condition_types_true(conditions: list[RancherCondition]) -> list[str]:
    """Return sorted condition types whose status is true."""

    return sorted(
        condition.type for condition in conditions if status_to_bool(condition.status) is True
    )
