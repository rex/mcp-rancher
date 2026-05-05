"""Shared normalization helpers for cluster-governance tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.governance import (
    RancherHorizontalPodAutoscalerSummary,
    RancherLimitRangeSummary,
    RancherResourceQuotaSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import mapping_value, string_dict, string_value


def _build_list_query_params(
    *,
    limit: int | None,
    continue_token: str | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed list query params for governance list calls."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if continue_token is not None:
        params["continue"] = continue_token
    if label_selector is not None:
        params["labelSelector"] = label_selector
    if field_selector is not None:
        params["fieldSelector"] = field_selector
    return params


def _items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    return object_items(payload, field="items")


def _hpa_metrics(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Pull spec.metrics[] from an HPA payload."""

    spec = mapping_value(payload, "spec") or {}
    raw = spec.get("metrics")
    if not isinstance(raw, list):
        return []
    return [
        cast(dict[str, object], item) for item in cast(list[object], raw) if isinstance(item, dict)
    ]


def _hpa_condition_status(payload: Mapping[str, object], condition_type: str) -> bool | None:
    """Read status.conditions[<type>].status as a boolean."""

    status = mapping_value(payload, "status") or {}
    raw = status.get("conditions")
    if not isinstance(raw, list):
        return None
    for raw_cond in cast(list[object], raw):
        if not isinstance(raw_cond, dict):
            continue
        cond = cast(dict[str, object], raw_cond)
        if string_value(cond, "type") == condition_type:
            return string_value(cond, "status") == "True"
    return None


def _hpa_metric_types(payload: Mapping[str, object]) -> list[str]:
    """Return sorted unique metric `type` strings from spec.metrics[]."""

    types = {
        string_value(metric, "type")
        for metric in _hpa_metrics(payload)
        if string_value(metric, "type") is not None
    }
    return sorted(t for t in types if t is not None)


def _hpa_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherHorizontalPodAutoscalerSummary:
    """Normalize one HPA payload — derive metric_count and condition booleans."""

    summary = RancherHorizontalPodAutoscalerSummary.model_validate(payload)
    return summary.model_copy(
        update={
            "metric_count": len(_hpa_metrics(payload)),
            "able_to_scale": _hpa_condition_status(payload, "AbleToScale"),
            "scaling_active": _hpa_condition_status(payload, "ScalingActive"),
        }
    )


def _resource_quota_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherResourceQuotaSummary:
    """Normalize one ResourceQuota payload."""

    summary = RancherResourceQuotaSummary.model_validate(payload)
    status = mapping_value(payload, "status") or {}
    hard = mapping_value(status, "hard") or {}
    used = mapping_value(status, "used") or {}
    return summary.model_copy(
        update={
            "hard_limit_count": len(string_dict(hard)),
            "used_count": len(string_dict(used)),
            "hard_limit_keys": sorted(string_dict(hard)),
        }
    )


def _limit_range_types_present(payload: Mapping[str, object]) -> list[str]:
    """Return sorted unique limit `type` strings from spec.limits[]."""

    spec = mapping_value(payload, "spec") or {}
    raw = spec.get("limits")
    if not isinstance(raw, list):
        return []
    types: set[str] = set()
    for raw_limit in cast(list[object], raw):
        if not isinstance(raw_limit, dict):
            continue
        limit = cast(dict[str, object], raw_limit)
        kind = string_value(limit, "type")
        if kind:
            types.add(kind)
    return sorted(types)


def _limit_count(payload: Mapping[str, object]) -> int:
    """Count the number of entries in spec.limits[]."""

    spec = mapping_value(payload, "spec") or {}
    raw = spec.get("limits")
    if not isinstance(raw, list):
        return 0
    return len(cast(list[object], raw))


def _limit_range_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherLimitRangeSummary:
    """Normalize one LimitRange payload."""

    summary = RancherLimitRangeSummary.model_validate(payload)
    return summary.model_copy(
        update={
            "limit_count": _limit_count(payload),
            "types_present": _limit_range_types_present(payload),
        }
    )


build_list_query_params = _build_list_query_params
hpa_metric_types = _hpa_metric_types
hpa_summary_from_payload = _hpa_summary_from_payload
items = _items
limit_range_summary_from_payload = _limit_range_summary_from_payload
resource_quota_summary_from_payload = _resource_quota_summary_from_payload
