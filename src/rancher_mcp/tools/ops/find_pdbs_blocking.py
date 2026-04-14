"""Find PDBs that currently block disruption."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.ops.failure_finders import PdbBlockersList, PdbBlockerSummary
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.ops.paths import k8s_items, k8s_policy_ns_path
from rancher_mcp.tools.support.values import (
    int_value,
    mapping_value,
    scalar_to_string,
    string_dict,
    string_value,
)


async def _find_pdbs_blocking(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    client: ManagementDiscoveryClient,
) -> PdbBlockersList:
    """Scan PDBs for zero-disruption-allowed state."""

    path = k8s_policy_ns_path(cluster_id, namespace, "poddisruptionbudgets")
    payload = await client.get_json(path)
    blockers: list[PdbBlockerSummary] = []

    for pdb in k8s_items(payload):
        metadata = mapping_value(pdb, "metadata") or {}
        spec = mapping_value(pdb, "spec") or {}
        status = mapping_value(pdb, "status") or {}
        disruptions_allowed = int_value(status, "disruptionsAllowed")
        if disruptions_allowed == 0:
            selector = mapping_value(spec, "selector") or {}
            match_labels = selector.get("matchLabels")
            blockers.append(
                PdbBlockerSummary(
                    name=string_value(metadata, "name") or "<unknown>",
                    namespace=string_value(metadata, "namespace") or namespace,
                    min_available=scalar_to_string(spec.get("minAvailable")),
                    max_unavailable=scalar_to_string(spec.get("maxUnavailable")),
                    current_healthy=int_value(status, "currentHealthy"),
                    desired_healthy=int_value(status, "desiredHealthy"),
                    disruptions_allowed=0,
                    selector_match_labels=string_dict(match_labels),
                )
            )

    return PdbBlockersList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        blocking_count=len(blockers),
        blockers=blockers,
    )


async def rancher_find_pdbs_blocking(
    namespace: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> PdbBlockersList:
    """Find PDBs that currently allow zero disruptions, blocking drain/eviction."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _find_pdbs_blocking(instance_name, cluster_id, namespace, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _find_pdbs_blocking(instance_name, cluster_id, namespace, managed_client)


async def rancher_find_pdbs_blocking_tool(
    namespace: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> PdbBlockersList:
    """Find PDBs blocking maintenance: currently allowing zero disruptions."""

    return await rancher_find_pdbs_blocking(
        namespace=namespace,
        cluster_id=cluster_id,
        instance=instance,
    )
