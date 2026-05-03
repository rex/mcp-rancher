"""Curated Rancher daemonset tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.workloads import RancherDaemonSetDetail, RancherDaemonSetList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import build_steve_list_query_params
from rancher_mcp.services.resources.builders_pagination import next_page_token_from_payload
from rancher_mcp.tools.support.values import mapping_value, string_dict
from rancher_mcp.tools.workloads.paths import workload_collection_path, workload_resource_path
from rancher_mcp.tools.workloads.shared import (
    daemonset_summary_from_payload,
    items,
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
    page_token: str | None = None,
) -> RancherDaemonSetList:
    """Fetch and normalize daemonsets through Rancher's raw Kubernetes proxy."""

    query_params = build_steve_list_query_params(
        limit=limit,
        continue_token=page_token,
        label_selector=label_selector,
        field_selector=field_selector,
    )
    payload = await client.get_json(
        workload_collection_path(cluster_id, namespace, "daemonsets"),
        params=query_params or None,
    )
    daemonsets = [daemonset_summary_from_payload(item) for item in items(payload)]
    if ready is not None:
        daemonsets = [daemonset for daemonset in daemonsets if daemonset.ready is ready]
    return RancherDaemonSetList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        daemonset_count=len(daemonsets),
        next_page_token=next_page_token_from_payload(payload),
        applied_query_params=query_params,
        daemonsets=daemonsets,
        suggested_next_steps=["rancher_daemonset_get", "rancher_pods_list"],
    )


async def rancher_daemonsets_list(
    namespace: str,
    cluster_id: str = "local",
    ready: bool | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    page_token: str | None = None,
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
            page_token,
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
            page_token,
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
    summary = daemonset_summary_from_payload(payload)
    metadata = mapping_value(payload, "metadata") or {}
    annotations = mapping_value(metadata, "annotations") or {}
    return RancherDaemonSetDetail.model_validate(payload).model_copy(
        update={
            "id": summary.id,
            "ready": summary.ready,
            "container_images": summary.container_images,
            "annotation_keys": sorted(string_dict(annotations)),
            "payload": dict(payload),
            "suggested_next_steps": ["rancher_daemonsets_list", "rancher_pods_list"],
        }
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
    page_token: str | None = None,
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
        page_token=page_token,
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
