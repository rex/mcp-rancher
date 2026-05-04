"""Shared normalization helpers for curated disruption tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.disruption import RancherPodDisruptionBudgetSummary
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.conditions import condition_is_true, conditions_from_payload
from rancher_mcp.tools.support.values import (
    int_value,
    mapping_value,
    scalar_to_string,
    string_dict,
)


def _build_list_query_params(
    *, limit: int | None, continue_token: str | None = None
) -> dict[str, str | int | bool]:
    """Build typed list query params for raw Kubernetes proxy PDB list calls."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if continue_token is not None:
        params["continue"] = continue_token
    return params


def _pdb_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherPodDisruptionBudgetSummary:
    """Normalize one pod disruption budget payload."""

    spec = mapping_value(payload, "spec") or {}
    status = mapping_value(payload, "status") or {}
    selector = mapping_value(mapping_value(spec, "selector"), "matchLabels") or {}
    conditions = conditions_from_payload(status)
    summary = RancherPodDisruptionBudgetSummary.model_validate(payload)
    return summary.model_copy(
        update={
            "id": (
                f"{summary.namespace}/{summary.name}"
                if summary.namespace and summary.name
                else summary.name or "<unknown-pdb>"
            ),
            "min_available": scalar_to_string(spec.get("minAvailable")),
            "max_unavailable": scalar_to_string(spec.get("maxUnavailable")),
            "current_healthy": int_value(status, "currentHealthy"),
            "desired_healthy": int_value(status, "desiredHealthy"),
            "expected_pods": int_value(status, "expectedPods"),
            "disruptions_allowed": int_value(status, "disruptionsAllowed"),
            "disruption_allowed": condition_is_true(conditions, "DisruptionAllowed"),
            "selector_match_labels": string_dict(selector),
        }
    )


def _items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    return object_items(payload, field="items")


build_list_query_params = _build_list_query_params
items = _items
pdb_summary_from_payload = _pdb_summary_from_payload
