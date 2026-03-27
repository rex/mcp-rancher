"""Curated Rancher workload-controller read-only tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from urllib.parse import quote

from mcp.server.fastmcp import FastMCP

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.models.workloads import (
    RancherDaemonSetDetail,
    RancherDaemonSetList,
    RancherDaemonSetSummary,
    RancherDeploymentDetail,
    RancherDeploymentList,
    RancherDeploymentSummary,
    RancherStatefulSetDetail,
    RancherStatefulSetList,
    RancherStatefulSetSummary,
    RancherWorkloadContainerSummary,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import build_steve_list_query_params


async def _fetch_deployments_list(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    ready: bool | None,
    limit: int | None,
    label_selector: str | None,
    field_selector: str | None,
    client: ManagementDiscoveryClient,
) -> RancherDeploymentList:
    """Fetch and normalize deployments through Rancher's raw Kubernetes proxy."""

    query_params = build_steve_list_query_params(
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
    )
    payload = await client.get_json(
        _workload_collection_path(cluster_id, namespace, "deployments"),
        params=query_params or None,
    )
    deployments = [_deployment_summary_from_payload(item) for item in _items(payload)]
    if ready is not None:
        deployments = [deployment for deployment in deployments if deployment.ready is ready]
    return RancherDeploymentList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        deployment_count=len(deployments),
        applied_query_params=query_params,
        deployments=deployments,
    )


async def rancher_deployments_list(
    namespace: str,
    cluster_id: str = "local",
    ready: bool | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherDeploymentList:
    """List deployments in one namespace with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_deployments_list(
            instance_name,
            cluster_id,
            namespace,
            ready,
            limit,
            label_selector,
            field_selector,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_deployments_list(
            instance_name,
            cluster_id,
            namespace,
            ready,
            limit,
            label_selector,
            field_selector,
            managed_client,
        )


async def _fetch_deployment_get(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    deployment_name: str,
    client: ManagementDiscoveryClient,
) -> RancherDeploymentDetail:
    """Fetch and normalize one deployment."""

    payload = await client.get_json(
        _workload_resource_path(cluster_id, namespace, "deployments", deployment_name)
    )
    summary = _deployment_summary_from_payload(payload)
    metadata = _mapping_value(payload, "metadata") or {}
    annotations = _mapping_value(metadata, "annotations") or {}
    spec = _mapping_value(payload, "spec") or {}
    status = _mapping_value(payload, "status") or {}
    template_spec = _template_spec(payload)
    return RancherDeploymentDetail(
        id=summary.id,
        name=summary.name,
        namespace=summary.namespace,
        desired_replicas=summary.desired_replicas,
        ready_replicas=summary.ready_replicas,
        available_replicas=summary.available_replicas,
        updated_replicas=summary.updated_replicas,
        unavailable_replicas=summary.unavailable_replicas,
        ready=summary.ready,
        rollout_complete=summary.rollout_complete,
        strategy_type=summary.strategy_type,
        paused=summary.paused,
        selector_match_labels=summary.selector_match_labels,
        container_images=summary.container_images,
        revision=_string_value(annotations, "deployment.kubernetes.io/revision"),
        generation=_int_value(metadata, "generation"),
        observed_generation=_int_value(status, "observedGeneration"),
        service_account_name=_string_value(template_spec, "serviceAccountName"),
        min_ready_seconds=_int_value(spec, "minReadySeconds"),
        annotation_keys=sorted(_string_dict(annotations)),
        conditions=_conditions_from_status(status),
        containers=_container_summaries(template_spec),
        payload=dict(payload),
    )


async def rancher_deployment_get(
    namespace: str,
    deployment_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherDeploymentDetail:
    """Fetch one deployment by namespace and name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_deployment_get(
            instance_name,
            cluster_id,
            namespace,
            deployment_name,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_deployment_get(
            instance_name,
            cluster_id,
            namespace,
            deployment_name,
            managed_client,
        )


async def _fetch_daemonsets_list(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    ready: bool | None,
    limit: int | None,
    label_selector: str | None,
    field_selector: str | None,
    client: ManagementDiscoveryClient,
) -> RancherDaemonSetList:
    """Fetch and normalize daemonsets through Rancher's raw Kubernetes proxy."""

    query_params = build_steve_list_query_params(
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
    )
    payload = await client.get_json(
        _workload_collection_path(cluster_id, namespace, "daemonsets"),
        params=query_params or None,
    )
    daemonsets = [_daemonset_summary_from_payload(item) for item in _items(payload)]
    if ready is not None:
        daemonsets = [daemonset for daemonset in daemonsets if daemonset.ready is ready]
    return RancherDaemonSetList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        daemonset_count=len(daemonsets),
        applied_query_params=query_params,
        daemonsets=daemonsets,
    )


async def rancher_daemonsets_list(
    namespace: str,
    cluster_id: str = "local",
    ready: bool | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherDaemonSetList:
    """List daemonsets in one namespace with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_daemonsets_list(
            instance_name,
            cluster_id,
            namespace,
            ready,
            limit,
            label_selector,
            field_selector,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_daemonsets_list(
            instance_name,
            cluster_id,
            namespace,
            ready,
            limit,
            label_selector,
            field_selector,
            managed_client,
        )


async def _fetch_daemonset_get(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    daemonset_name: str,
    client: ManagementDiscoveryClient,
) -> RancherDaemonSetDetail:
    """Fetch and normalize one daemonset."""

    payload = await client.get_json(
        _workload_resource_path(cluster_id, namespace, "daemonsets", daemonset_name)
    )
    summary = _daemonset_summary_from_payload(payload)
    metadata = _mapping_value(payload, "metadata") or {}
    annotations = _mapping_value(metadata, "annotations") or {}
    status = _mapping_value(payload, "status") or {}
    template_spec = _template_spec(payload)
    return RancherDaemonSetDetail(
        id=summary.id,
        name=summary.name,
        namespace=summary.namespace,
        desired_number_scheduled=summary.desired_number_scheduled,
        current_number_scheduled=summary.current_number_scheduled,
        number_ready=summary.number_ready,
        number_available=summary.number_available,
        number_unavailable=summary.number_unavailable,
        updated_number_scheduled=summary.updated_number_scheduled,
        ready=summary.ready,
        strategy_type=summary.strategy_type,
        selector_match_labels=summary.selector_match_labels,
        container_images=summary.container_images,
        generation=_int_value(metadata, "generation"),
        observed_generation=_int_value(status, "observedGeneration"),
        service_account_name=_string_value(template_spec, "serviceAccountName"),
        annotation_keys=sorted(_string_dict(annotations)),
        conditions=_conditions_from_status(status),
        containers=_container_summaries(template_spec),
        payload=dict(payload),
    )


async def rancher_daemonset_get(
    namespace: str,
    daemonset_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherDaemonSetDetail:
    """Fetch one daemonset by namespace and name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_daemonset_get(
            instance_name,
            cluster_id,
            namespace,
            daemonset_name,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_daemonset_get(
            instance_name,
            cluster_id,
            namespace,
            daemonset_name,
            managed_client,
        )


async def _fetch_statefulsets_list(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    ready: bool | None,
    limit: int | None,
    label_selector: str | None,
    field_selector: str | None,
    client: ManagementDiscoveryClient,
) -> RancherStatefulSetList:
    """Fetch and normalize statefulsets through Rancher's raw Kubernetes proxy."""

    query_params = build_steve_list_query_params(
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
    )
    payload = await client.get_json(
        _workload_collection_path(cluster_id, namespace, "statefulsets"),
        params=query_params or None,
    )
    statefulsets = [_statefulset_summary_from_payload(item) for item in _items(payload)]
    if ready is not None:
        statefulsets = [statefulset for statefulset in statefulsets if statefulset.ready is ready]
    return RancherStatefulSetList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        statefulset_count=len(statefulsets),
        applied_query_params=query_params,
        statefulsets=statefulsets,
    )


async def rancher_statefulsets_list(
    namespace: str,
    cluster_id: str = "local",
    ready: bool | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherStatefulSetList:
    """List statefulsets in one namespace with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_statefulsets_list(
            instance_name,
            cluster_id,
            namespace,
            ready,
            limit,
            label_selector,
            field_selector,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_statefulsets_list(
            instance_name,
            cluster_id,
            namespace,
            ready,
            limit,
            label_selector,
            field_selector,
            managed_client,
        )


async def _fetch_statefulset_get(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    statefulset_name: str,
    client: ManagementDiscoveryClient,
) -> RancherStatefulSetDetail:
    """Fetch and normalize one statefulset."""

    payload = await client.get_json(
        _workload_resource_path(cluster_id, namespace, "statefulsets", statefulset_name)
    )
    summary = _statefulset_summary_from_payload(payload)
    metadata = _mapping_value(payload, "metadata") or {}
    annotations = _mapping_value(metadata, "annotations") or {}
    status = _mapping_value(payload, "status") or {}
    template_spec = _template_spec(payload)
    return RancherStatefulSetDetail(
        id=summary.id,
        name=summary.name,
        namespace=summary.namespace,
        replicas=summary.replicas,
        ready_replicas=summary.ready_replicas,
        current_replicas=summary.current_replicas,
        updated_replicas=summary.updated_replicas,
        available_replicas=summary.available_replicas,
        ready=summary.ready,
        service_name=summary.service_name,
        update_strategy_type=summary.update_strategy_type,
        selector_match_labels=summary.selector_match_labels,
        container_images=summary.container_images,
        generation=_int_value(metadata, "generation"),
        observed_generation=_int_value(status, "observedGeneration"),
        current_revision=_string_value(status, "currentRevision"),
        update_revision=_string_value(status, "updateRevision"),
        service_account_name=_string_value(template_spec, "serviceAccountName"),
        annotation_keys=sorted(_string_dict(annotations)),
        conditions=_conditions_from_status(status),
        containers=_container_summaries(template_spec),
        payload=dict(payload),
    )


async def rancher_statefulset_get(
    namespace: str,
    statefulset_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherStatefulSetDetail:
    """Fetch one statefulset by namespace and name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_statefulset_get(
            instance_name,
            cluster_id,
            namespace,
            statefulset_name,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_statefulset_get(
            instance_name,
            cluster_id,
            namespace,
            statefulset_name,
            managed_client,
        )


def register_workload_tools(mcp: FastMCP) -> None:
    """Register curated workload-controller tools with the FastMCP server."""

    mcp.tool(name="rancher_deployments_list")(rancher_deployments_list_tool)
    mcp.tool(name="rancher_deployment_get")(rancher_deployment_get_tool)
    mcp.tool(name="rancher_daemonsets_list")(rancher_daemonsets_list_tool)
    mcp.tool(name="rancher_daemonset_get")(rancher_daemonset_get_tool)
    mcp.tool(name="rancher_statefulsets_list")(rancher_statefulsets_list_tool)
    mcp.tool(name="rancher_statefulset_get")(rancher_statefulset_get_tool)


async def rancher_deployments_list_tool(
    namespace: str,
    cluster_id: str = "local",
    ready: bool | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
) -> RancherDeploymentList:
    """Public MCP wrapper for curated deployment list."""

    return await rancher_deployments_list(
        namespace=namespace,
        cluster_id=cluster_id,
        ready=ready,
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
        instance=instance,
    )


async def rancher_deployment_get_tool(
    namespace: str,
    deployment_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherDeploymentDetail:
    """Public MCP wrapper for curated deployment detail."""

    return await rancher_deployment_get(
        namespace=namespace,
        deployment_name=deployment_name,
        cluster_id=cluster_id,
        instance=instance,
    )


async def rancher_daemonsets_list_tool(
    namespace: str,
    cluster_id: str = "local",
    ready: bool | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
) -> RancherDaemonSetList:
    """Public MCP wrapper for curated daemonset list."""

    return await rancher_daemonsets_list(
        namespace=namespace,
        cluster_id=cluster_id,
        ready=ready,
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
        instance=instance,
    )


async def rancher_daemonset_get_tool(
    namespace: str,
    daemonset_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherDaemonSetDetail:
    """Public MCP wrapper for curated daemonset detail."""

    return await rancher_daemonset_get(
        namespace=namespace,
        daemonset_name=daemonset_name,
        cluster_id=cluster_id,
        instance=instance,
    )


async def rancher_statefulsets_list_tool(
    namespace: str,
    cluster_id: str = "local",
    ready: bool | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
) -> RancherStatefulSetList:
    """Public MCP wrapper for curated statefulset list."""

    return await rancher_statefulsets_list(
        namespace=namespace,
        cluster_id=cluster_id,
        ready=ready,
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
        instance=instance,
    )


async def rancher_statefulset_get_tool(
    namespace: str,
    statefulset_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherStatefulSetDetail:
    """Public MCP wrapper for curated statefulset detail."""

    return await rancher_statefulset_get(
        namespace=namespace,
        statefulset_name=statefulset_name,
        cluster_id=cluster_id,
        instance=instance,
    )


def _workload_collection_path(cluster_id: str, namespace: str, resource: str) -> str:
    """Build the raw Kubernetes proxy collection path for one workload resource."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/apps/v1/namespaces/"
        f"{quote(namespace, safe='')}/{quote(resource, safe='')}"
    )


def _workload_resource_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
) -> str:
    """Build the raw Kubernetes proxy resource path for one workload object."""

    return f"{_workload_collection_path(cluster_id, namespace, resource)}/{quote(name, safe='')}"


def _deployment_summary_from_payload(payload: Mapping[str, object]) -> RancherDeploymentSummary:
    """Normalize one deployment payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    spec = _mapping_value(payload, "spec") or {}
    status = _mapping_value(payload, "status") or {}
    desired_replicas = _int_value(spec, "replicas")
    ready_replicas = _int_value(status, "readyReplicas")
    available_replicas = _int_value(status, "availableReplicas")
    updated_replicas = _int_value(status, "updatedReplicas")
    unavailable_replicas = _int_value(status, "unavailableReplicas")
    generation = _int_value(metadata, "generation")
    observed_generation = _int_value(status, "observedGeneration")
    paused = _bool_value(spec, "paused")
    selector_match_labels = _selector_match_labels(spec)
    container_images = _container_images(_template_spec(payload))
    return RancherDeploymentSummary(
        id=_namespaced_id(metadata, "deployment"),
        name=_string_value(metadata, "name") or "<unknown-deployment>",
        namespace=_string_value(metadata, "namespace") or "<unknown-namespace>",
        desired_replicas=desired_replicas,
        ready_replicas=ready_replicas,
        available_replicas=available_replicas,
        updated_replicas=updated_replicas,
        unavailable_replicas=unavailable_replicas,
        ready=_deployment_ready(desired_replicas, ready_replicas, available_replicas),
        rollout_complete=_deployment_rollout_complete(
            desired_replicas=desired_replicas,
            ready_replicas=ready_replicas,
            available_replicas=available_replicas,
            updated_replicas=updated_replicas,
            generation=generation,
            observed_generation=observed_generation,
            paused=paused,
        ),
        strategy_type=_string_value(_mapping_value(spec, "strategy"), "type"),
        paused=paused,
        selector_match_labels=selector_match_labels,
        container_images=container_images,
    )


def _daemonset_summary_from_payload(payload: Mapping[str, object]) -> RancherDaemonSetSummary:
    """Normalize one daemonset payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    spec = _mapping_value(payload, "spec") or {}
    status = _mapping_value(payload, "status") or {}
    desired_number_scheduled = _int_value(status, "desiredNumberScheduled")
    current_number_scheduled = _int_value(status, "currentNumberScheduled")
    number_ready = _int_value(status, "numberReady")
    number_available = _int_value(status, "numberAvailable")
    number_unavailable = _int_value(status, "numberUnavailable")
    updated_number_scheduled = _int_value(status, "updatedNumberScheduled")
    return RancherDaemonSetSummary(
        id=_namespaced_id(metadata, "daemonset"),
        name=_string_value(metadata, "name") or "<unknown-daemonset>",
        namespace=_string_value(metadata, "namespace") or "<unknown-namespace>",
        desired_number_scheduled=desired_number_scheduled,
        current_number_scheduled=current_number_scheduled,
        number_ready=number_ready,
        number_available=number_available,
        number_unavailable=number_unavailable,
        updated_number_scheduled=updated_number_scheduled,
        ready=_daemonset_ready(
            desired_number_scheduled=desired_number_scheduled,
            number_ready=number_ready,
            updated_number_scheduled=updated_number_scheduled,
        ),
        strategy_type=_string_value(_mapping_value(spec, "updateStrategy"), "type"),
        selector_match_labels=_selector_match_labels(spec),
        container_images=_container_images(_template_spec(payload)),
    )


def _statefulset_summary_from_payload(payload: Mapping[str, object]) -> RancherStatefulSetSummary:
    """Normalize one statefulset payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    spec = _mapping_value(payload, "spec") or {}
    status = _mapping_value(payload, "status") or {}
    replicas = _int_value(spec, "replicas")
    ready_replicas = _int_value(status, "readyReplicas")
    current_replicas = _int_value(status, "currentReplicas")
    updated_replicas = _int_value(status, "updatedReplicas")
    available_replicas = _int_value(status, "availableReplicas")
    return RancherStatefulSetSummary(
        id=_namespaced_id(metadata, "statefulset"),
        name=_string_value(metadata, "name") or "<unknown-statefulset>",
        namespace=_string_value(metadata, "namespace") or "<unknown-namespace>",
        replicas=replicas,
        ready_replicas=ready_replicas,
        current_replicas=current_replicas,
        updated_replicas=updated_replicas,
        available_replicas=available_replicas,
        ready=_statefulset_ready(
            replicas=replicas,
            ready_replicas=ready_replicas,
            updated_replicas=updated_replicas,
        ),
        service_name=_string_value(spec, "serviceName"),
        update_strategy_type=_string_value(_mapping_value(spec, "updateStrategy"), "type"),
        selector_match_labels=_selector_match_labels(spec),
        container_images=_container_images(_template_spec(payload)),
    )


def _deployment_ready(
    desired_replicas: int | None,
    ready_replicas: int | None,
    available_replicas: int | None,
) -> bool | None:
    """Return whether a deployment has the desired ready and available replicas."""

    if desired_replicas is None:
        return None
    return (
        ready_replicas is not None
        and ready_replicas >= desired_replicas
        and available_replicas is not None
        and available_replicas >= desired_replicas
    )


def _deployment_rollout_complete(
    *,
    desired_replicas: int | None,
    ready_replicas: int | None,
    available_replicas: int | None,
    updated_replicas: int | None,
    generation: int | None,
    observed_generation: int | None,
    paused: bool | None,
) -> bool | None:
    """Return whether a deployment rollout appears fully converged."""

    if desired_replicas is None or paused is True:
        return None if desired_replicas is None else False
    if generation is None or observed_generation is None:
        return None
    return (
        observed_generation >= generation
        and updated_replicas is not None
        and updated_replicas >= desired_replicas
        and ready_replicas is not None
        and ready_replicas >= desired_replicas
        and available_replicas is not None
        and available_replicas >= desired_replicas
    )


def _daemonset_ready(
    *,
    desired_number_scheduled: int | None,
    number_ready: int | None,
    updated_number_scheduled: int | None,
) -> bool | None:
    """Return whether a daemonset has converged across all desired nodes."""

    if desired_number_scheduled is None:
        return None
    return (
        number_ready is not None
        and number_ready >= desired_number_scheduled
        and updated_number_scheduled is not None
        and updated_number_scheduled >= desired_number_scheduled
    )


def _statefulset_ready(
    *,
    replicas: int | None,
    ready_replicas: int | None,
    updated_replicas: int | None,
) -> bool | None:
    """Return whether a statefulset appears to have all desired ready replicas."""

    if replicas is None:
        return None
    return (
        ready_replicas is not None
        and ready_replicas >= replicas
        and updated_replicas is not None
        and updated_replicas >= replicas
    )


def _template_spec(payload: Mapping[str, object]) -> dict[str, object]:
    """Return one workload template pod spec when present."""

    spec = _mapping_value(payload, "spec") or {}
    template = _mapping_value(spec, "template") or {}
    return _mapping_value(template, "spec") or {}


def _selector_match_labels(spec: Mapping[str, object]) -> dict[str, str]:
    """Return selector matchLabels from a workload spec."""

    selector = _mapping_value(spec, "selector") or {}
    return _string_dict(_mapping_value(selector, "matchLabels") or {})


def _container_summaries(
    template_spec: Mapping[str, object],
) -> list[RancherWorkloadContainerSummary]:
    """Return typed workload-template container summaries."""

    raw_containers = template_spec.get("containers")
    if not isinstance(raw_containers, list):
        return []
    summaries: list[RancherWorkloadContainerSummary] = []
    typed_containers = cast(list[object], raw_containers)
    for raw_container in typed_containers:
        if not isinstance(raw_container, dict):
            continue
        container = cast(dict[str, object], raw_container)
        name = _string_value(container, "name")
        if name is None:
            continue
        summaries.append(
            RancherWorkloadContainerSummary(
                name=name,
                image=_string_value(container, "image"),
            )
        )
    return summaries


def _container_images(template_spec: Mapping[str, object]) -> list[str]:
    """Return the unique image list from a workload template pod spec."""

    images: list[str] = []
    for container in _container_summaries(template_spec):
        if container.image is not None:
            images.append(container.image)
    return sorted(set(images))


def _conditions_from_status(status: Mapping[str, object]) -> list[RancherCondition]:
    """Normalize workload conditions from a status payload."""

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


def _namespaced_id(metadata: Mapping[str, object], fallback_kind: str) -> str:
    """Return a stable namespace/name identifier for one namespaced workload."""

    name = _string_value(metadata, "name") or f"<unknown-{fallback_kind}>"
    namespace = _string_value(metadata, "namespace") or "<unknown-namespace>"
    return f"{namespace}/{name}"


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


def _bool_value(payload: Mapping[str, object] | None, key: str) -> bool | None:
    """Read one boolean value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, bool) else None


def _string_dict(value: object) -> dict[str, str]:
    """Normalize an arbitrary value into a string-to-string mapping."""

    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, raw_value in cast(dict[object, object], value).items():
        if isinstance(key, str) and isinstance(raw_value, str):
            result[key] = raw_value
    return result
