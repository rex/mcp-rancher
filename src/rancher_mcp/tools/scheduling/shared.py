"""Shared normalization helpers for cluster scheduling tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.scheduling import (
    RancherPriorityClassSummary,
    RancherRuntimeClassSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import mapping_value, string_dict, string_value


def _build_list_query_params(
    *,
    limit: int | None,
    continue_token: str | None = None,
    label_selector: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed list query params for scheduling list calls."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if continue_token is not None:
        params["continue"] = continue_token
    if label_selector is not None:
        params["labelSelector"] = label_selector
    return params


def _items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    return object_items(payload, field="items")


def _priority_class_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherPriorityClassSummary:
    """Normalize one PriorityClass payload."""

    summary = RancherPriorityClassSummary.model_validate(payload)
    value = payload.get("value") if isinstance(payload.get("value"), int) else None
    description = string_value(payload, "description")
    return summary.model_copy(update={"value": value, "description": description})


def _runtime_class_overhead_keys(payload: Mapping[str, object]) -> list[str]:
    """Pull spec.overhead.podFixed key names as a sorted list."""

    overhead = mapping_value(payload, "overhead") or {}
    pod_fixed = mapping_value(overhead, "podFixed") or {}
    return sorted(string_dict(pod_fixed))


def _runtime_class_node_selector_keys(payload: Mapping[str, object]) -> list[str]:
    """Pull spec.scheduling.nodeSelector key names as a sorted list."""

    scheduling = mapping_value(payload, "scheduling") or {}
    selector = mapping_value(scheduling, "nodeSelector") or {}
    return sorted(string_dict(selector))


def _runtime_class_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherRuntimeClassSummary:
    """Normalize one RuntimeClass payload — derive overhead + scheduling-selector key lists."""

    summary = RancherRuntimeClassSummary.model_validate(payload)
    handler = string_value(payload, "handler")
    return summary.model_copy(
        update={
            "handler": handler,
            "overhead_pod_fixed_keys": _runtime_class_overhead_keys(payload),
            "scheduling_node_selector_keys": _runtime_class_node_selector_keys(payload),
        }
    )


build_list_query_params = _build_list_query_params
items = _items
priority_class_summary_from_payload = _priority_class_summary_from_payload
runtime_class_summary_from_payload = _runtime_class_summary_from_payload
