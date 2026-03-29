"""Curated Rancher namespace tools."""

from __future__ import annotations

from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.projects_namespaces import RancherNamespaceDetail, RancherNamespaceList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.projects_namespaces.shared import (
    build_namespace_query_params,
    data_items,
    namespace_cattle_conditions,
    namespace_summary_from_payload,
    string_dict,
    string_list,
)
from rancher_mcp.tools.support.values import mapping_value


async def _fetch_namespaces_list(
    instance_name: str,
    cluster_id: str,
    phase: str | None,
    project_id: str | None,
    limit: int | None,
    label_selector: str | None,
    field_selector: str | None,
    client: SteveDiscoveryClient,
) -> RancherNamespaceList:
    """Fetch and normalize downstream namespaces."""

    query_params = build_namespace_query_params(
        project_id=project_id,
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
    )
    payload = await client.get_json("/namespaces", params=query_params or None)
    namespaces = [namespace_summary_from_payload(cluster_id, item) for item in data_items(payload)]
    if phase is not None:
        namespaces = [namespace for namespace in namespaces if namespace.phase == phase]
    return RancherNamespaceList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace_count=len(namespaces),
        applied_query_params=query_params,
        namespaces=namespaces,
    )


async def rancher_namespaces_list(
    cluster_id: str = "local",
    phase: str | None = None,
    project_id: str | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> RancherNamespaceList:
    """List downstream namespaces with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_namespaces_list(
            instance_name,
            cluster_id,
            phase,
            project_id,
            limit,
            label_selector,
            field_selector,
            client,
        )
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as steve_client:
        return await _fetch_namespaces_list(
            instance_name,
            cluster_id,
            phase,
            project_id,
            limit,
            label_selector,
            field_selector,
            steve_client,
        )


async def _fetch_namespace_get(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    client: SteveDiscoveryClient,
) -> RancherNamespaceDetail:
    """Fetch and normalize one downstream namespace."""

    payload = await client.get_json(f"/namespaces/{namespace}")
    summary = namespace_summary_from_payload(cluster_id, payload)
    metadata = mapping_value(payload, "metadata") or {}
    annotations = mapping_value(metadata, "annotations") or {}
    labels = mapping_value(metadata, "labels") or {}
    return RancherNamespaceDetail(
        id=summary.id,
        name=summary.name,
        cluster_id=summary.cluster_id,
        phase=summary.phase,
        state_name=summary.state_name,
        state_message=summary.state_message,
        state_error=summary.state_error,
        project_id=summary.project_id,
        project_id_short=summary.project_id_short,
        finalizer_count=summary.finalizer_count,
        label_keys=sorted(string_dict(labels)),
        annotation_keys=sorted(string_dict(annotations)),
        finalizers=string_list(metadata.get("finalizers")),
        cattle_conditions=namespace_cattle_conditions(metadata),
        link_keys=sorted(mapping_value(payload, "links") or {}),
        payload=dict(payload),
    )


async def rancher_namespace_get(
    namespace: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> RancherNamespaceDetail:
    """Fetch one downstream namespace by name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_namespace_get(instance_name, cluster_id, namespace, client)
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as steve_client:
        return await _fetch_namespace_get(instance_name, cluster_id, namespace, steve_client)


async def rancher_namespaces_list_tool(
    cluster_id: str = "local",
    phase: str | None = None,
    project_id: str | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
) -> RancherNamespaceList:
    """Public MCP wrapper for curated namespace list."""

    return await rancher_namespaces_list(
        cluster_id=cluster_id,
        phase=phase,
        project_id=project_id,
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
        instance=instance,
    )


async def rancher_namespace_get_tool(
    namespace: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherNamespaceDetail:
    """Public MCP wrapper for curated namespace detail."""

    return await rancher_namespace_get(
        namespace=namespace,
        cluster_id=cluster_id,
        instance=instance,
    )
