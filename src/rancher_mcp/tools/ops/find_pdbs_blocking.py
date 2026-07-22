"""Find PDBs that currently block disruption."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.ops.failure_finders import PdbBlockersList, PdbBlockerSummary
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.ops.paths import k8s_items, k8s_policy_path
from rancher_mcp.tools.support.conditions import conditions_from_value, first_false_condition
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
    namespace: str | None,
    client: ManagementDiscoveryClient,
) -> PdbBlockersList:
    """Scan PDBs for zero-disruption-allowed state — one namespace or cluster-wide."""

    path = k8s_policy_path(cluster_id, "poddisruptionbudgets", namespace)
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
            # PDB status.conditions carries `DisruptionAllowed: False` (with a
            # reason like "InsufficientPods") on API servers that populate it
            # (policy/v1) — read defensively so reason/message/since/ageDays
            # surface when present rather than guessing on older servers
            # (M-B1/B2; no 2.6.5 regression, this is purely additive).
            problem = first_false_condition(conditions_from_value(status.get("conditions")))
            blockers.append(
                PdbBlockerSummary(
                    name=string_value(metadata, "name") or "<unknown>",
                    namespace=string_value(metadata, "namespace") or "<unknown>",
                    min_available=scalar_to_string(spec.get("minAvailable")),
                    max_unavailable=scalar_to_string(spec.get("maxUnavailable")),
                    current_healthy=int_value(status, "currentHealthy"),
                    desired_healthy=int_value(status, "desiredHealthy"),
                    disruptions_allowed=0,
                    selector_match_labels=string_dict(match_labels),
                    reason=problem.reason if problem else None,
                    message=problem.message if problem else None,
                    since=problem.since if problem else None,
                    age_days=problem.age_days if problem else None,
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
    namespace: str | None = None,
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
    namespace: str | None = None,
    cluster_id: str = "local",
    instance: str | None = None,
) -> PdbBlockersList:
    """Scan pod disruption budgets that currently allow zero voluntary evictions and
    report each with its healthy and desired counts plus the blocking reason —
    explains why a drain or rollout is stuck waiting.

    Omit `namespace` to sweep the entire cluster in one call.
    """

    return await rancher_find_pdbs_blocking(
        namespace=namespace,
        cluster_id=cluster_id,
        instance=instance,
    )
