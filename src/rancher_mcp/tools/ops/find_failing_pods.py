"""Find failing pods in a namespace."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.ops.failure_finders import FailingPodsList, FailingPodSummary
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.ops.paths import k8s_core_path, k8s_items
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.conditions import condition_is_true, conditions_from_value
from rancher_mcp.tools.support.values import mapping_value, string_value

_FAILING_PHASES = frozenset({"Failed", "Unknown"})
_FAILING_CONTAINER_STATES = frozenset(
    {
        "CrashLoopBackOff",
        "ImagePullBackOff",
        "ErrImagePull",
        "CreateContainerConfigError",
        "InvalidImageName",
        "RunContainerError",
    }
)


def _container_problem_states(status: dict[str, object]) -> list[str]:
    """Extract container waiting reasons that indicate failure."""

    states: list[str] = []
    for container_status in object_items(status, field="containerStatuses"):
        state_obj = mapping_value(container_status, "state")
        if state_obj is None:
            continue
        waiting = mapping_value(state_obj, "waiting")
        if waiting is not None:
            reason = string_value(waiting, "reason")
            if reason and reason in _FAILING_CONTAINER_STATES:
                states.append(reason)
        terminated = mapping_value(state_obj, "terminated")
        if terminated is not None:
            reason = string_value(terminated, "reason")
            if reason == "Error":
                states.append("Error")
    return states


def _total_restarts(status: dict[str, object]) -> int:
    """Sum restart counts across all containers."""

    total = 0
    for container_status in object_items(status, field="containerStatuses"):
        restart_count = container_status.get("restartCount")
        if isinstance(restart_count, int) and not isinstance(restart_count, bool):
            total += restart_count
    return total


async def _find_failing_pods(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    client: ManagementDiscoveryClient,
) -> FailingPodsList:
    """Scan pods for failures — one namespace, or the whole cluster if None."""

    path = k8s_core_path(cluster_id, "pods", namespace)
    payload = await client.get_json(path)
    failing: list[FailingPodSummary] = []

    for pod in k8s_items(payload):
        metadata = mapping_value(pod, "metadata") or {}
        status = mapping_value(pod, "status") or {}
        phase = string_value(status, "phase")
        container_states = _container_problem_states(status)

        is_failing = phase in _FAILING_PHASES or phase == "Pending" or len(container_states) > 0
        if not is_failing:
            conditions = conditions_from_value(status.get("conditions"))
            if condition_is_true(conditions, "Ready") is False and phase == "Running":
                is_failing = True
                container_states = ["NotReady"]

        if is_failing:
            owner_kind = None
            owner_name = None
            owner_refs = object_items(metadata, field="ownerReferences")
            if owner_refs:
                owner_kind = string_value(owner_refs[0], "kind")
                owner_name = string_value(owner_refs[0], "name")

            reason = string_value(status, "reason")
            spec = mapping_value(pod, "spec") or {}
            failing.append(
                FailingPodSummary(
                    name=string_value(metadata, "name") or "<unknown>",
                    namespace=string_value(metadata, "namespace") or "<unknown>",
                    phase=phase,
                    reason=reason or (container_states[0] if container_states else None),
                    node_name=string_value(spec, "nodeName"),
                    owner_kind=owner_kind,
                    owner_name=owner_name,
                    restart_count=_total_restarts(status),
                    container_states=container_states,
                )
            )

    return FailingPodsList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        failing_count=len(failing),
        pods=failing,
    )


async def rancher_find_failing_pods(
    namespace: str | None = None,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> FailingPodsList:
    """Find pods in trouble: CrashLoopBackOff, Pending, Failed, ImagePullBackOff, NotReady."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _find_failing_pods(instance_name, cluster_id, namespace, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _find_failing_pods(instance_name, cluster_id, namespace, managed_client)


async def rancher_find_failing_pods_tool(
    namespace: str | None = None,
    cluster_id: str = "local",
    instance: str | None = None,
) -> FailingPodsList:
    """Find failing pods (CrashLoopBackOff, Pending, Failed, ImagePull errors).

    Omit `namespace` to triage the entire cluster in one call; pass it to
    scope to a single namespace.
    """

    return await rancher_find_failing_pods(
        namespace=namespace,
        cluster_id=cluster_id,
        instance=instance,
    )
