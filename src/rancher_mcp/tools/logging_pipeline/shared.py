"""Shared normalization helpers for Banzai logging-pipeline tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.logging_pipeline import (
    RancherLoggingClusterFlowSummary,
    RancherLoggingClusterOutputSummary,
    RancherLoggingFlowSummary,
    RancherLoggingOutputSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import mapping_value

# Spec keys that are NOT output-type indicators.
_OUTPUT_NON_TYPE_KEYS = frozenset({"loggingRef"})


def _build_list_query_params(
    *,
    limit: int | None,
    continue_token: str | None = None,
    label_selector: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed list query params for Banzai logging-pipeline list calls."""

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


def _detect_output_type(payload: Mapping[str, object]) -> str | None:
    """Return the first non-loggingRef key in spec — typically the destination kind."""

    spec = mapping_value(payload, "spec") or {}
    for key, value in spec.items():
        if key in _OUTPUT_NON_TYPE_KEYS:
            continue
        if isinstance(value, dict):
            return key
    return None


def _output_summary_from_payload(payload: Mapping[str, object]) -> RancherLoggingOutputSummary:
    """Normalize one Output payload."""

    summary = RancherLoggingOutputSummary.model_validate(payload)
    return summary.model_copy(update={"output_type": _detect_output_type(payload)})


def _cluster_output_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherLoggingClusterOutputSummary:
    """Normalize one ClusterOutput payload."""

    summary = RancherLoggingClusterOutputSummary.model_validate(payload)
    return summary.model_copy(update={"output_type": _detect_output_type(payload)})


def _flow_match_filter_counts(payload: Mapping[str, object]) -> tuple[int, int]:
    """Return (match_count, filter_count) for a Flow / ClusterFlow payload."""

    spec = mapping_value(payload, "spec") or {}
    raw_match = spec.get("match")
    raw_filters = spec.get("filters")
    match_count = len(cast(list[object], raw_match)) if isinstance(raw_match, list) else 0
    filter_count = len(cast(list[object], raw_filters)) if isinstance(raw_filters, list) else 0
    return match_count, filter_count


def _flow_summary_from_payload(payload: Mapping[str, object]) -> RancherLoggingFlowSummary:
    """Normalize one Flow payload."""

    summary = RancherLoggingFlowSummary.model_validate(payload)
    match_count, filter_count = _flow_match_filter_counts(payload)
    return summary.model_copy(update={"match_count": match_count, "filter_count": filter_count})


def _cluster_flow_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherLoggingClusterFlowSummary:
    """Normalize one ClusterFlow payload."""

    summary = RancherLoggingClusterFlowSummary.model_validate(payload)
    match_count, filter_count = _flow_match_filter_counts(payload)
    return summary.model_copy(update={"match_count": match_count, "filter_count": filter_count})


build_list_query_params = _build_list_query_params
cluster_flow_summary_from_payload = _cluster_flow_summary_from_payload
cluster_output_summary_from_payload = _cluster_output_summary_from_payload
flow_summary_from_payload = _flow_summary_from_payload
items = _items
output_summary_from_payload = _output_summary_from_payload
