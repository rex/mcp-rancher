"""Find PVCs that are not bound."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.ops.failure_finders import UnboundPvcsList, UnboundPvcSummary
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.ops.paths import k8s_core_path, k8s_items
from rancher_mcp.tools.support.conditions import conditions_from_value, first_false_condition
from rancher_mcp.tools.support.values import mapping_value, string_value


async def _find_unbound_pvcs(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    client: ManagementDiscoveryClient,
) -> UnboundPvcsList:
    """Scan PVCs for non-Bound phase — one namespace or the whole cluster."""

    path = k8s_core_path(cluster_id, "persistentvolumeclaims", namespace)
    payload = await client.get_json(path)
    unbound: list[UnboundPvcSummary] = []

    for pvc in k8s_items(payload):
        metadata = mapping_value(pvc, "metadata") or {}
        spec = mapping_value(pvc, "spec") or {}
        status = mapping_value(pvc, "status") or {}
        phase = string_value(status, "phase")
        if phase == "Bound":
            continue
        resources = mapping_value(spec, "resources") or {}
        requests = mapping_value(resources, "requests") or {}
        # PVC status.conditions is real API surface (mainly CSI resize/
        # provisioning signals) but inconsistently populated — read it
        # defensively so reason/message/since/ageDays surface *when the
        # payload has them* rather than guessing a value (M-B1/B2).
        problem = first_false_condition(conditions_from_value(status.get("conditions")))
        unbound.append(
            UnboundPvcSummary(
                name=string_value(metadata, "name") or "<unknown>",
                namespace=string_value(metadata, "namespace") or "<unknown>",
                phase=phase,
                storage_class=string_value(spec, "storageClassName"),
                requested_storage=string_value(requests, "storage"),
                reason=problem.reason if problem else None,
                message=problem.message if problem else None,
                since=problem.since if problem else None,
                age_days=problem.age_days if problem else None,
            )
        )

    return UnboundPvcsList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        unbound_count=len(unbound),
        pvcs=unbound,
    )


async def rancher_find_unbound_pvcs(
    namespace: str | None = None,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> UnboundPvcsList:
    """Find PVCs that are not bound: Pending, Lost, or otherwise unhealthy."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _find_unbound_pvcs(instance_name, cluster_id, namespace, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _find_unbound_pvcs(instance_name, cluster_id, namespace, managed_client)


async def rancher_find_unbound_pvcs_tool(
    namespace: str | None = None,
    cluster_id: str = "local",
    instance: str | None = None,
) -> UnboundPvcsList:
    """Scan persistent volume claims stuck outside the Bound phase and report each
    with its storage class, requested size, and stall reason — the quickest way
    to spot storage blocking a pod from starting.

    Omit `namespace` to sweep the entire cluster at once.
    """

    return await rancher_find_unbound_pvcs(
        namespace=namespace,
        cluster_id=cluster_id,
        instance=instance,
    )
