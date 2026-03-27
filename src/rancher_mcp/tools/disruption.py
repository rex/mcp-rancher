"""Curated Rancher disruption-management read-only tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from urllib.parse import quote

from mcp.server.fastmcp import FastMCP

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.models.disruption import (
    RancherPodDisruptionBudgetDetail,
    RancherPodDisruptionBudgetList,
    RancherPodDisruptionBudgetSummary,
)
from rancher_mcp.services.instances import resolve_instance


async def _fetch_pod_disruption_budgets_list(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    limit: int | None,
    client: ManagementDiscoveryClient,
) -> RancherPodDisruptionBudgetList:
    """Fetch and normalize PDBs through Rancher's raw Kubernetes proxy."""

    query_params = _build_list_query_params(limit=limit)
    payload = await client.get_json(
        _pdb_collection_path(cluster_id, namespace),
        params=query_params or None,
    )
    budgets = [_pdb_summary_from_payload(item) for item in _items(payload)]
    return RancherPodDisruptionBudgetList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        budget_count=len(budgets),
        applied_query_params=query_params,
        pod_disruption_budgets=budgets,
    )


async def rancher_pod_disruption_budgets_list(
    namespace: str,
    cluster_id: str = "local",
    limit: int | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherPodDisruptionBudgetList:
    """List pod disruption budgets in one namespace with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_pod_disruption_budgets_list(
            instance_name,
            cluster_id,
            namespace,
            limit,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_pod_disruption_budgets_list(
            instance_name,
            cluster_id,
            namespace,
            limit,
            managed_client,
        )


async def _fetch_pod_disruption_budget_get(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    budget_name: str,
    client: ManagementDiscoveryClient,
) -> RancherPodDisruptionBudgetDetail:
    """Fetch and normalize one pod disruption budget."""

    payload = await client.get_json(_pdb_resource_path(cluster_id, namespace, budget_name))
    summary = _pdb_summary_from_payload(payload)
    metadata = _mapping_value(payload, "metadata") or {}
    return RancherPodDisruptionBudgetDetail(
        id=summary.id,
        name=summary.name,
        namespace=summary.namespace,
        min_available=summary.min_available,
        max_unavailable=summary.max_unavailable,
        current_healthy=summary.current_healthy,
        desired_healthy=summary.desired_healthy,
        expected_pods=summary.expected_pods,
        disruptions_allowed=summary.disruptions_allowed,
        disruption_allowed=summary.disruption_allowed,
        selector_match_labels=summary.selector_match_labels,
        annotation_keys=sorted(_string_dict(_mapping_value(metadata, "annotations") or {})),
        conditions=_conditions_from_status(_mapping_value(payload, "status") or {}),
        payload=dict(payload),
    )


async def rancher_pod_disruption_budget_get(
    namespace: str,
    budget_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherPodDisruptionBudgetDetail:
    """Fetch one pod disruption budget by namespace and name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_pod_disruption_budget_get(
            instance_name,
            cluster_id,
            namespace,
            budget_name,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_pod_disruption_budget_get(
            instance_name,
            cluster_id,
            namespace,
            budget_name,
            managed_client,
        )


def register_disruption_tools(mcp: FastMCP) -> None:
    """Register curated disruption-management tools with the FastMCP server."""

    mcp.tool(name="rancher_pod_disruption_budgets_list")(rancher_pod_disruption_budgets_list_tool)
    mcp.tool(name="rancher_pod_disruption_budget_get")(rancher_pod_disruption_budget_get_tool)


async def rancher_pod_disruption_budgets_list_tool(
    namespace: str,
    cluster_id: str = "local",
    limit: int | None = None,
    instance: str | None = None,
) -> RancherPodDisruptionBudgetList:
    """Public MCP wrapper for curated PDB list."""

    return await rancher_pod_disruption_budgets_list(
        namespace=namespace,
        cluster_id=cluster_id,
        limit=limit,
        instance=instance,
    )


async def rancher_pod_disruption_budget_get_tool(
    namespace: str,
    budget_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherPodDisruptionBudgetDetail:
    """Public MCP wrapper for curated PDB detail."""

    return await rancher_pod_disruption_budget_get(
        namespace=namespace,
        budget_name=budget_name,
        cluster_id=cluster_id,
        instance=instance,
    )


def _build_list_query_params(*, limit: int | None) -> dict[str, str | int | bool]:
    """Build typed list query params for raw Kubernetes proxy PDB list calls."""

    if limit is None:
        return {}
    return {"limit": limit}


def _pdb_collection_path(cluster_id: str, namespace: str) -> str:
    """Build the raw Kubernetes proxy collection path for namespaced PDBs."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/policy/v1/namespaces/"
        f"{quote(namespace, safe='')}/poddisruptionbudgets"
    )


def _pdb_resource_path(cluster_id: str, namespace: str, budget_name: str) -> str:
    """Build the raw Kubernetes proxy resource path for one PDB."""

    return f"{_pdb_collection_path(cluster_id, namespace)}/{quote(budget_name, safe='')}"


def _pdb_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherPodDisruptionBudgetSummary:
    """Normalize one pod disruption budget payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    spec = _mapping_value(payload, "spec") or {}
    status = _mapping_value(payload, "status") or {}
    selector = _mapping_value(_mapping_value(spec, "selector"), "matchLabels") or {}
    return RancherPodDisruptionBudgetSummary(
        id=(
            f"{_string_value(metadata, 'namespace')}/{_string_value(metadata, 'name')}"
            if _string_value(metadata, "namespace") and _string_value(metadata, "name")
            else _string_value(metadata, "name") or "<unknown-pdb>"
        ),
        name=_string_value(metadata, "name") or "<unknown-pdb>",
        namespace=_string_value(metadata, "namespace") or "<unknown-namespace>",
        min_available=_scalar_to_string(spec.get("minAvailable")),
        max_unavailable=_scalar_to_string(spec.get("maxUnavailable")),
        current_healthy=_int_value(status, "currentHealthy"),
        desired_healthy=_int_value(status, "desiredHealthy"),
        expected_pods=_int_value(status, "expectedPods"),
        disruptions_allowed=_int_value(status, "disruptionsAllowed"),
        disruption_allowed=_condition_status_bool(status, "DisruptionAllowed"),
        selector_match_labels=_string_dict(selector),
    )


def _conditions_from_status(status: Mapping[str, object]) -> list[RancherCondition]:
    """Normalize PDB conditions from a status payload."""

    raw_conditions = status.get("conditions")
    if not isinstance(raw_conditions, list):
        return []
    conditions: list[RancherCondition] = []
    typed_conditions = cast(list[object], raw_conditions)
    for raw_condition in typed_conditions:
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


def _condition_status_bool(status: Mapping[str, object], condition_type: str) -> bool | None:
    """Return one named PDB condition as a boolean when present."""

    for condition in _conditions_from_status(status):
        if condition.type == condition_type:
            return _status_to_bool(condition.status)
    return None


def _items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, object]] = []
    typed_items = cast(list[object], raw_items)
    for item in typed_items:
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


def _int_value(payload: Mapping[str, object] | None, key: str) -> int | None:
    """Read one integer value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, int) else None


def _string_dict(value: object) -> dict[str, str]:
    """Normalize an arbitrary value into a string-to-string mapping."""

    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, raw_value in cast(dict[object, object], value).items():
        if isinstance(key, str) and isinstance(raw_value, str):
            result[key] = raw_value
    return result


def _scalar_to_string(value: object) -> str | None:
    """Normalize an int-or-string field into a string representation."""

    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    return None


def _status_to_bool(value: str | None) -> bool | None:
    """Normalize Kubernetes-style string booleans to actual booleans."""

    if value is None:
        return None
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None
