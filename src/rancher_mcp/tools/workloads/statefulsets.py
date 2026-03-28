# pyright: reportPrivateUsage=false
"""Curated Rancher statefulset tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.workloads import RancherStatefulSetDetail, RancherStatefulSetList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import build_steve_list_query_params
from rancher_mcp.tools.workloads.paths import workload_collection_path, workload_resource_path
from rancher_mcp.tools.workloads.shared import (
    _conditions_from_status,
    _container_summaries,
    _int_value,
    _items,
    _mapping_value,
    _statefulset_summary_from_payload,
    _string_dict,
    _string_value,
    _template_spec,
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
        workload_collection_path(cluster_id, namespace, "statefulsets"),
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
        workload_resource_path(cluster_id, namespace, "statefulsets", statefulset_name)
    )
    summary = _statefulset_summary_from_payload(payload)
    metadata = _mapping_value(payload, "metadata") or {}
    annotations = _mapping_value(metadata, "annotations") or {}
    status = _mapping_value(payload, "status") or {}
    template_spec_value = _template_spec(payload)
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
        service_account_name=_string_value(template_spec_value, "serviceAccountName"),
        annotation_keys=sorted(_string_dict(annotations)),
        conditions=_conditions_from_status(status),
        containers=_container_summaries(template_spec_value),
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
