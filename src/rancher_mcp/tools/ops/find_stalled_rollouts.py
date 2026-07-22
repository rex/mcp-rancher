"""Find deployments and statefulsets that are not converging."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.ops.failure_finders import StalledRolloutsList, StalledRolloutSummary
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.ops.paths import k8s_apps_path, k8s_items
from rancher_mcp.tools.support.conditions import conditions_from_value
from rancher_mcp.tools.support.derive import age_days
from rancher_mcp.tools.support.values import mapping_value, string_value
from rancher_mcp.tools.workloads.shared import deployment_rollout_diagnosis


def _safe_int(value: object) -> int:
    """Coerce a raw payload value to int, defaulting to 0."""

    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def _rollout_diagnosis(
    status: dict[str, object],
) -> tuple[str | None, str | None, str | None, int | None]:
    """Derive (reason, message, since, ageDays) from a workload's own conditions.

    Reuses ``deployment_rollout_diagnosis`` (M-B1/B2, ``tools/workloads/
    shared.py``) — the exact same "why is this rollout stuck" pick
    ``deployments_list`` already surfaces (M-A7) — plus ``derive.age_days``
    for the day count, so neither the condition-priority logic nor the
    day-count math is re-derived here.
    """

    conditions = conditions_from_value(status.get("conditions"))
    reason, message, since = deployment_rollout_diagnosis(conditions)
    return reason, message, since, age_days(since)


async def _find_stalled_rollouts(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    client: ManagementDiscoveryClient,
) -> StalledRolloutsList:
    """Scan deployments and statefulsets — one namespace or the whole cluster."""

    stalled: list[StalledRolloutSummary] = []

    deploy_path = k8s_apps_path(cluster_id, "deployments", namespace)
    deploy_payload = await client.get_json(deploy_path)
    for dep in k8s_items(deploy_payload):
        metadata = mapping_value(dep, "metadata") or {}
        spec = mapping_value(dep, "spec") or {}
        status = mapping_value(dep, "status") or {}
        desired = _safe_int(spec.get("replicas"))
        ready = _safe_int(status.get("readyReplicas"))
        updated = _safe_int(status.get("updatedReplicas"))
        unavailable = status.get("unavailableReplicas")

        if desired > 0 and (ready < desired or updated < desired):
            reason, message, since, item_age_days = _rollout_diagnosis(status)
            stalled.append(
                StalledRolloutSummary(
                    name=string_value(metadata, "name") or "<unknown>",
                    namespace=string_value(metadata, "namespace") or "<unknown>",
                    kind="Deployment",
                    desired_replicas=desired,
                    ready_replicas=ready,
                    updated_replicas=updated,
                    unavailable_replicas=(
                        _safe_int(unavailable) if unavailable is not None else None
                    ),
                    reason=reason,
                    message=message,
                    since=since,
                    age_days=item_age_days,
                )
            )

    sts_path = k8s_apps_path(cluster_id, "statefulsets", namespace)
    sts_payload = await client.get_json(sts_path)
    for sts in k8s_items(sts_payload):
        metadata = mapping_value(sts, "metadata") or {}
        spec = mapping_value(sts, "spec") or {}
        status = mapping_value(sts, "status") or {}
        desired = _safe_int(spec.get("replicas"))
        ready = _safe_int(status.get("readyReplicas"))
        updated = _safe_int(status.get("updatedReplicas"))

        if desired > 0 and (ready < desired or updated < desired):
            reason, message, since, item_age_days = _rollout_diagnosis(status)
            stalled.append(
                StalledRolloutSummary(
                    name=string_value(metadata, "name") or "<unknown>",
                    namespace=string_value(metadata, "namespace") or "<unknown>",
                    kind="StatefulSet",
                    desired_replicas=desired,
                    ready_replicas=ready,
                    updated_replicas=updated,
                    reason=reason,
                    message=message,
                    since=since,
                    age_days=item_age_days,
                )
            )

    return StalledRolloutsList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        stalled_count=len(stalled),
        rollouts=stalled,
    )


async def rancher_find_stalled_rollouts(
    namespace: str | None = None,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> StalledRolloutsList:
    """Find deployments and statefulsets that are not converging."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _find_stalled_rollouts(instance_name, cluster_id, namespace, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _find_stalled_rollouts(instance_name, cluster_id, namespace, managed_client)


async def rancher_find_stalled_rollouts_tool(
    namespace: str | None = None,
    cluster_id: str = "local",
    instance: str | None = None,
) -> StalledRolloutsList:
    """Find stalled rollouts (deployments/statefulsets not converging).

    Omit `namespace` to scan the whole cluster; pass it to scope to one.
    """

    return await rancher_find_stalled_rollouts(
        namespace=namespace,
        cluster_id=cluster_id,
        instance=instance,
    )
