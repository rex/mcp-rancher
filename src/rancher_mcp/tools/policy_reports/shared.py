"""Shared normalization helpers for PolicyReport tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.policy_reports import (
    RancherClusterPolicyReportSummary,
    RancherPolicyReportSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import string_value


def _build_list_query_params(
    *,
    limit: int | None,
    continue_token: str | None = None,
    label_selector: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed list query params for PolicyReport list calls."""

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


def _result_stats(payload: Mapping[str, object]) -> tuple[int, list[str]]:
    """Return (result_count, top_failing_policies) for a PolicyReport payload."""

    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        return 0, []
    results = cast(list[object], raw_results)
    result_count = len(results)
    failing: set[str] = set()
    for raw_result in results:
        if not isinstance(raw_result, dict):
            continue
        result = cast(dict[str, object], raw_result)
        if string_value(result, "result") == "fail":
            policy = string_value(result, "policy")
            if policy:
                failing.add(policy)
    return result_count, sorted(failing)


def _policy_report_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherPolicyReportSummary:
    """Normalize one PolicyReport payload."""

    summary = RancherPolicyReportSummary.model_validate(payload)
    result_count, top_failing = _result_stats(payload)
    return summary.model_copy(
        update={
            "result_count": result_count,
            "top_failing_policies": top_failing,
        }
    )


def _cluster_policy_report_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherClusterPolicyReportSummary:
    """Normalize one ClusterPolicyReport payload."""

    summary = RancherClusterPolicyReportSummary.model_validate(payload)
    result_count, top_failing = _result_stats(payload)
    return summary.model_copy(
        update={
            "result_count": result_count,
            "top_failing_policies": top_failing,
        }
    )


build_list_query_params = _build_list_query_params
cluster_policy_report_summary_from_payload = _cluster_policy_report_summary_from_payload
items = _items
policy_report_summary_from_payload = _policy_report_summary_from_payload
