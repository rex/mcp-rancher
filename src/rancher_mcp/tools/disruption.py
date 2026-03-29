"""Curated Rancher disruption-management read-only tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.disruption import (
    RancherPodDisruptionBudgetDetail,
    RancherPodDisruptionBudgetList,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.disruption_support import (
    build_list_query_params as _build_list_query_params,
)
from rancher_mcp.tools.disruption_support import (
    items as _items,
)
from rancher_mcp.tools.disruption_support import (
    mapping_value as _mapping_value,
)
from rancher_mcp.tools.disruption_support import (
    pdb_collection_path as _pdb_collection_path,
)
from rancher_mcp.tools.disruption_support import (
    pdb_resource_path as _pdb_resource_path,
)
from rancher_mcp.tools.disruption_support import (
    pdb_summary_from_payload as _pdb_summary_from_payload,
)
from rancher_mcp.tools.disruption_support import (
    string_dict as _string_dict,
)


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
    return RancherPodDisruptionBudgetDetail.model_validate(payload).model_copy(
        update={
            "id": summary.id,
            "disruption_allowed": summary.disruption_allowed,
            "annotation_keys": sorted(_string_dict(_mapping_value(metadata, "annotations") or {})),
            "payload": dict(payload),
        }
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
