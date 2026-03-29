"""Curated Rancher deployment tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.workloads import RancherDeploymentDetail, RancherDeploymentList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import build_steve_list_query_params
from rancher_mcp.tools.support.values import mapping_value, string_value
from rancher_mcp.tools.workloads.paths import workload_collection_path, workload_resource_path
from rancher_mcp.tools.workloads.shared import (
    conditions_from_status,
    container_summaries,
    deployment_summary_from_payload,
    int_value,
    items,
    string_dict,
    template_spec,
)


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
        workload_collection_path(cluster_id, namespace, "deployments"),
        params=query_params or None,
    )
    deployments = [deployment_summary_from_payload(item) for item in items(payload)]
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
        workload_resource_path(cluster_id, namespace, "deployments", deployment_name)
    )
    summary = deployment_summary_from_payload(payload)
    metadata = mapping_value(payload, "metadata") or {}
    annotations = mapping_value(metadata, "annotations") or {}
    spec = mapping_value(payload, "spec") or {}
    status = mapping_value(payload, "status") or {}
    template_spec_value = template_spec(payload)
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
        revision=string_value(annotations, "deployment.kubernetes.io/revision"),
        generation=int_value(metadata, "generation"),
        observed_generation=int_value(status, "observedGeneration"),
        service_account_name=string_value(template_spec_value, "serviceAccountName"),
        min_ready_seconds=int_value(spec, "minReadySeconds"),
        annotation_keys=sorted(string_dict(annotations)),
        conditions=conditions_from_status(status),
        containers=container_summaries(template_spec_value),
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
