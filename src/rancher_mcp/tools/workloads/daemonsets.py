# pyright: reportPrivateUsage=false
"""Curated Rancher daemonset tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.workloads import RancherDaemonSetDetail, RancherDaemonSetList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import build_steve_list_query_params
from rancher_mcp.tools.workloads.paths import workload_collection_path, workload_resource_path
from rancher_mcp.tools.workloads.shared import (
    _conditions_from_status,
    _container_summaries,
    _daemonset_summary_from_payload,
    _int_value,
    _items,
    _mapping_value,
    _string_dict,
    _string_value,
    _template_spec,
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
        workload_collection_path(cluster_id, namespace, "daemonsets"),
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
        workload_resource_path(cluster_id, namespace, "daemonsets", daemonset_name)
    )
    summary = _daemonset_summary_from_payload(payload)
    metadata = _mapping_value(payload, "metadata") or {}
    annotations = _mapping_value(metadata, "annotations") or {}
    status = _mapping_value(payload, "status") or {}
    template_spec_value = _template_spec(payload)
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
        service_account_name=_string_value(template_spec_value, "serviceAccountName"),
        annotation_keys=sorted(_string_dict(annotations)),
        conditions=_conditions_from_status(status),
        containers=_container_summaries(template_spec_value),
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
