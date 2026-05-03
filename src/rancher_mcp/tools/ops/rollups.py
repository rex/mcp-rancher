"""Namespace and project rollup convenience tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.ops.rollups import (
    NamespaceWorkloadsSummary,
    ProjectHealthSummary,
    WorkloadControllerCounts,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.ops.paths import k8s_apps_ns_path, k8s_core_ns_path, k8s_items
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import mapping_value, string_value
from rancher_mcp.tools.workloads.readiness import (
    daemonset_ready,
    deployment_rollout_complete,
    statefulset_ready,
)


def _safe_int(value: object) -> int:
    """Coerce a raw payload value to int, defaulting to 0."""

    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def _spec(payload: dict[str, object]) -> dict[str, object]:
    """Return a resource spec mapping or an empty mapping."""

    return mapping_value(payload, "spec") or {}


def _status(payload: dict[str, object]) -> dict[str, object]:
    """Return a resource status mapping or an empty mapping."""

    return mapping_value(payload, "status") or {}


def _metadata(payload: dict[str, object]) -> dict[str, object]:
    """Return a resource metadata mapping or an empty mapping."""

    return mapping_value(payload, "metadata") or {}


async def _build_namespace_workloads(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    client: ManagementDiscoveryClient,
) -> NamespaceWorkloadsSummary:
    """Aggregate pod and workload controller health for one namespace."""

    pod_path = k8s_core_ns_path(cluster_id, namespace, "pods")
    pod_payload = await client.get_json(pod_path)
    pods = k8s_items(pod_payload)
    running = pending = failed = 0
    for pod in pods:
        status = mapping_value(pod, "status") or {}
        phase = string_value(status, "phase")
        if phase == "Running":
            running += 1
        elif phase == "Pending":
            pending += 1
        elif phase == "Failed":
            failed += 1

    dep_path = k8s_apps_ns_path(cluster_id, namespace, "deployments")
    dep_payload = await client.get_json(dep_path)
    dep_items = k8s_items(dep_payload)
    dep_ready = sum(
        1
        for deployment in dep_items
        if deployment_rollout_complete(
            desired_replicas=_safe_int(_spec(deployment).get("replicas")),
            ready_replicas=_safe_int(_status(deployment).get("readyReplicas")),
            available_replicas=_safe_int(_status(deployment).get("availableReplicas")),
            updated_replicas=_safe_int(_status(deployment).get("updatedReplicas")),
            generation=_safe_int(_metadata(deployment).get("generation")),
            observed_generation=_safe_int(_status(deployment).get("observedGeneration")),
            paused=_spec(deployment).get("paused") is True,
        )
        is True
    )

    ds_path = k8s_apps_ns_path(cluster_id, namespace, "daemonsets")
    ds_payload = await client.get_json(ds_path)
    ds_items = k8s_items(ds_payload)
    ds_ready = sum(
        1
        for daemonset in ds_items
        if daemonset_ready(
            desired_number_scheduled=_safe_int(_status(daemonset).get("desiredNumberScheduled")),
            number_ready=_safe_int(_status(daemonset).get("numberReady")),
            updated_number_scheduled=_safe_int(_status(daemonset).get("updatedNumberScheduled")),
        )
        is True
    )

    sts_path = k8s_apps_ns_path(cluster_id, namespace, "statefulsets")
    sts_payload = await client.get_json(sts_path)
    sts_items = k8s_items(sts_payload)
    sts_ready = sum(
        1
        for statefulset in sts_items
        if statefulset_ready(
            replicas=_safe_int(_spec(statefulset).get("replicas")),
            ready_replicas=_safe_int(_status(statefulset).get("readyReplicas")),
            updated_replicas=_safe_int(_status(statefulset).get("updatedReplicas")),
        )
        is True
    )

    wc = WorkloadControllerCounts(
        deployments_total=len(dep_items),
        deployments_ready=dep_ready,
        deployments_not_ready=len(dep_items) - dep_ready,
        daemonsets_total=len(ds_items),
        daemonsets_ready=ds_ready,
        daemonsets_not_ready=len(ds_items) - ds_ready,
        statefulsets_total=len(sts_items),
        statefulsets_ready=sts_ready,
        statefulsets_not_ready=len(sts_items) - sts_ready,
    )

    return NamespaceWorkloadsSummary(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        pod_count=len(pods),
        pods_running=running,
        pods_pending=pending,
        pods_failed=failed,
        workloads=wc,
    )


async def rancher_namespace_workloads_summary(
    namespace: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> NamespaceWorkloadsSummary:
    """One-call namespace workload rollup: pods, deployments, daemonsets, statefulsets."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _build_namespace_workloads(instance_name, cluster_id, namespace, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _build_namespace_workloads(
            instance_name,
            cluster_id,
            namespace,
            managed_client,
        )


async def rancher_namespace_workloads_summary_tool(
    namespace: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> NamespaceWorkloadsSummary:
    """One-call namespace workload rollup with pod counts and controller readiness."""

    return await rancher_namespace_workloads_summary(
        namespace=namespace,
        cluster_id=cluster_id,
        instance=instance,
    )


async def _build_project_health(
    instance_name: str,
    project_id: str,
    client: ManagementDiscoveryClient,
    ctx: Context[Any, Any, Any] | None = None,
) -> ProjectHealthSummary:
    """Fetch one project and its namespaces, compute health summary."""

    if ctx:
        await ctx.report_progress(0, 2)
    project_payload = await client.get_json(f"/v3/projects/{project_id}")
    project_name = string_value(project_payload, "name") or project_id
    state = string_value(project_payload, "state")
    cluster_id = string_value(project_payload, "clusterId")

    if ctx:
        await ctx.report_progress(1, 2)
    ns_payload = await client.get_json(
        "/v3/namespaces",
        params={"projectId": project_id},
    )
    ns_items = object_items(ns_payload, field="data")
    ns_names = [
        string_value(ns, "name") or string_value(ns, "id") or "<unknown>" for ns in ns_items
    ]

    total_pods = 0
    failing_pods = 0
    total_workloads = 0
    unhealthy_workloads = 0

    for ns_name in ns_names:
        if cluster_id is None:
            continue
        pod_path = k8s_core_ns_path(cluster_id, ns_name, "pods")
        pod_payload = await client.get_json(pod_path)
        pods = k8s_items(pod_payload)
        total_pods += len(pods)
        for pod in pods:
            status = mapping_value(pod, "status") or {}
            phase = string_value(status, "phase")
            if phase in ("Failed", "Unknown", "Pending"):
                failing_pods += 1

        dep_payload = await client.get_json(k8s_apps_ns_path(cluster_id, ns_name, "deployments"))
        deployments = k8s_items(dep_payload)
        total_workloads += len(deployments)
        for deployment in deployments:
            if (
                deployment_rollout_complete(
                    desired_replicas=_safe_int(_spec(deployment).get("replicas")),
                    ready_replicas=_safe_int(_status(deployment).get("readyReplicas")),
                    available_replicas=_safe_int(_status(deployment).get("availableReplicas")),
                    updated_replicas=_safe_int(_status(deployment).get("updatedReplicas")),
                    generation=_safe_int(_metadata(deployment).get("generation")),
                    observed_generation=_safe_int(_status(deployment).get("observedGeneration")),
                    paused=_spec(deployment).get("paused") is True,
                )
                is not True
            ):
                unhealthy_workloads += 1

        ds_payload = await client.get_json(k8s_apps_ns_path(cluster_id, ns_name, "daemonsets"))
        daemonsets = k8s_items(ds_payload)
        total_workloads += len(daemonsets)
        for daemonset in daemonsets:
            if (
                daemonset_ready(
                    desired_number_scheduled=_safe_int(
                        _status(daemonset).get("desiredNumberScheduled")
                    ),
                    number_ready=_safe_int(_status(daemonset).get("numberReady")),
                    updated_number_scheduled=_safe_int(
                        _status(daemonset).get("updatedNumberScheduled")
                    ),
                )
                is not True
            ):
                unhealthy_workloads += 1

        sts_payload = await client.get_json(k8s_apps_ns_path(cluster_id, ns_name, "statefulsets"))
        statefulsets = k8s_items(sts_payload)
        total_workloads += len(statefulsets)
        for statefulset in statefulsets:
            if (
                statefulset_ready(
                    replicas=_safe_int(_spec(statefulset).get("replicas")),
                    ready_replicas=_safe_int(_status(statefulset).get("readyReplicas")),
                    updated_replicas=_safe_int(_status(statefulset).get("updatedReplicas")),
                )
                is not True
            ):
                unhealthy_workloads += 1

    return ProjectHealthSummary(
        instance=instance_name,
        project_id=project_id,
        project_name=project_name,
        state=state,
        cluster_id=cluster_id,
        namespace_count=len(ns_names),
        namespaces=ns_names,
        total_pods=total_pods,
        failing_pods=failing_pods,
        total_workloads=total_workloads,
        unhealthy_workloads=unhealthy_workloads,
    )


async def rancher_project_health_summary(
    project_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
    ctx: Context[Any, Any, Any] | None = None,
) -> ProjectHealthSummary:
    """One-call project health: state, namespaces, failing pods, unhealthy workloads."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _build_project_health(instance_name, project_id, client, ctx)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _build_project_health(instance_name, project_id, managed_client, ctx)


async def rancher_project_health_summary_tool(
    project_id: str,
    instance: str | None = None,
    ctx: Context[Any, Any, Any] | None = None,
) -> ProjectHealthSummary:
    """One-call project health overview: state, namespaces, pods, and workload readiness."""

    return await rancher_project_health_summary(
        project_id=project_id,
        instance=instance,
        ctx=ctx,
    )
