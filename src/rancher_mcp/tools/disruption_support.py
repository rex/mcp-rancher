"""Normalization helpers for curated pod disruption budget tools."""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import quote

from rancher_mcp.models.disruption import RancherPodDisruptionBudgetSummary
from rancher_mcp.tools._support.collections import object_items
from rancher_mcp.tools._support.conditions import condition_is_true, conditions_from_payload
from rancher_mcp.tools._support.values import (
    int_value,
    mapping_value,
    scalar_to_string,
    string_dict,
    string_value,
)


def build_list_query_params(*, limit: int | None) -> dict[str, str | int | bool]:
    """Build typed list query params for raw Kubernetes proxy PDB list calls."""

    if limit is None:
        return {}
    return {"limit": limit}


def pdb_collection_path(cluster_id: str, namespace: str) -> str:
    """Build the raw Kubernetes proxy collection path for namespaced PDBs."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/policy/v1/namespaces/"
        f"{quote(namespace, safe='')}/poddisruptionbudgets"
    )


def pdb_resource_path(cluster_id: str, namespace: str, budget_name: str) -> str:
    """Build the raw Kubernetes proxy resource path for one PDB."""

    return f"{pdb_collection_path(cluster_id, namespace)}/{quote(budget_name, safe='')}"


def pdb_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherPodDisruptionBudgetSummary:
    """Normalize one pod disruption budget payload."""

    metadata = mapping_value(payload, "metadata") or {}
    spec = mapping_value(payload, "spec") or {}
    status = mapping_value(payload, "status") or {}
    selector = mapping_value(mapping_value(spec, "selector"), "matchLabels") or {}
    conditions = conditions_from_payload(status)
    return RancherPodDisruptionBudgetSummary(
        id=(
            f"{string_value(metadata, 'namespace')}/{string_value(metadata, 'name')}"
            if string_value(metadata, "namespace") and string_value(metadata, "name")
            else string_value(metadata, "name") or "<unknown-pdb>"
        ),
        name=string_value(metadata, "name") or "<unknown-pdb>",
        namespace=string_value(metadata, "namespace") or "<unknown-namespace>",
        min_available=scalar_to_string(spec.get("minAvailable")),
        max_unavailable=scalar_to_string(spec.get("maxUnavailable")),
        current_healthy=int_value(status, "currentHealthy"),
        desired_healthy=int_value(status, "desiredHealthy"),
        expected_pods=int_value(status, "expectedPods"),
        disruptions_allowed=int_value(status, "disruptionsAllowed"),
        disruption_allowed=condition_is_true(conditions, "DisruptionAllowed"),
        selector_match_labels=string_dict(selector),
    )


__all__ = [
    "build_list_query_params",
    "conditions_from_payload",
    "items",
    "mapping_value",
    "pdb_collection_path",
    "pdb_resource_path",
    "pdb_summary_from_payload",
    "string_dict",
]


def items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    return object_items(payload, field="items")
