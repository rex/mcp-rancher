# pyright: reportPrivateUsage=false
"""Curated Rancher service tools."""

from __future__ import annotations

from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.pods_services import RancherServiceDetail, RancherServiceList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import build_steve_list_query_params
from rancher_mcp.tools.pods_services.shared import (
    _data_items,
    _mapping_value,
    _relationship_types,
    _service_summary_from_payload,
    _string_list,
    _string_value,
)


async def _fetch_services_list(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    limit: int | None,
    label_selector: str | None,
    client: SteveDiscoveryClient,
) -> RancherServiceList:
    """Fetch and normalize the services collection for one namespace."""

    query_params = build_steve_list_query_params(limit=limit, label_selector=label_selector)
    payload = await client.get_json(f"/services/{namespace}", params=query_params or None)
    services = [_service_summary_from_payload(item) for item in _data_items(payload)]
    return RancherServiceList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        service_count=len(services),
        applied_query_params=query_params,
        services=services,
    )


async def rancher_services_list(
    namespace: str,
    cluster_id: str = "local",
    limit: int | None = None,
    label_selector: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> RancherServiceList:
    """List services in one namespace with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_services_list(
            instance_name,
            cluster_id,
            namespace,
            limit,
            label_selector,
            client,
        )
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as steve_client:
        return await _fetch_services_list(
            instance_name,
            cluster_id,
            namespace,
            limit,
            label_selector,
            steve_client,
        )


async def _fetch_service_get(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    service_name: str,
    client: SteveDiscoveryClient,
) -> RancherServiceDetail:
    """Fetch and normalize one service."""

    payload = await client.get_json(f"/services/{namespace}/{service_name}")
    summary = _service_summary_from_payload(payload)
    spec = _mapping_value(payload, "spec") or {}
    metadata = _mapping_value(payload, "metadata") or {}
    return RancherServiceDetail(
        id=summary.id,
        name=summary.name,
        namespace=summary.namespace,
        service_type=summary.service_type,
        cluster_ip=summary.cluster_ip,
        state_name=summary.state_name,
        state_message=summary.state_message,
        selector=summary.selector,
        ports=summary.ports,
        session_affinity=_string_value(spec, "sessionAffinity"),
        internal_traffic_policy=_string_value(spec, "internalTrafficPolicy"),
        external_ips=_string_list(spec.get("externalIPs")),
        relationship_types=_relationship_types(metadata),
        link_keys=sorted(_mapping_value(payload, "links") or {}),
        payload=dict(payload),
    )


async def rancher_service_get(
    namespace: str,
    service_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> RancherServiceDetail:
    """Fetch one service by namespace and name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_service_get(instance_name, cluster_id, namespace, service_name, client)
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as steve_client:
        return await _fetch_service_get(
            instance_name,
            cluster_id,
            namespace,
            service_name,
            steve_client,
        )


async def rancher_services_list_tool(
    namespace: str,
    cluster_id: str = "local",
    limit: int | None = None,
    label_selector: str | None = None,
    instance: str | None = None,
) -> RancherServiceList:
    """Public MCP wrapper for curated service list."""

    return await rancher_services_list(
        namespace=namespace,
        cluster_id=cluster_id,
        limit=limit,
        label_selector=label_selector,
        instance=instance,
    )


async def rancher_service_get_tool(
    namespace: str,
    service_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherServiceDetail:
    """Public MCP wrapper for curated service detail."""

    return await rancher_service_get(
        namespace=namespace,
        service_name=service_name,
        cluster_id=cluster_id,
        instance=instance,
    )
