# pyright: reportPrivateUsage=false
"""Curated Rancher pod tools."""

from __future__ import annotations

from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.pods_services import RancherPodDetail, RancherPodList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import build_steve_list_query_params
from rancher_mcp.tools.pods_services.shared import (
    _conditions_from_status,
    _container_summaries,
    _data_items,
    _mapping_value,
    _pod_summary_from_payload,
    _string_value,
)


async def _fetch_pods_list(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    phase: str | None,
    limit: int | None,
    label_selector: str | None,
    field_selector: str | None,
    client: SteveDiscoveryClient,
) -> RancherPodList:
    """Fetch and normalize the pods collection for one namespace."""

    query_params = build_steve_list_query_params(
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
    )
    payload = await client.get_json(f"/pods/{namespace}", params=query_params or None)
    pods = [_pod_summary_from_payload(item) for item in _data_items(payload)]
    if phase is not None:
        pods = [pod for pod in pods if pod.phase == phase]
    return RancherPodList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        pod_count=len(pods),
        applied_query_params=query_params,
        pods=pods,
    )


async def rancher_pods_list(
    namespace: str,
    cluster_id: str = "local",
    phase: str | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> RancherPodList:
    """List pods in one namespace with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_pods_list(
            instance_name,
            cluster_id,
            namespace,
            phase,
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
        return await _fetch_pods_list(
            instance_name,
            cluster_id,
            namespace,
            phase,
            limit,
            label_selector,
            field_selector,
            steve_client,
        )


async def _fetch_pod_get(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    pod_name: str,
    client: SteveDiscoveryClient,
) -> RancherPodDetail:
    """Fetch and normalize one pod."""

    payload = await client.get_json(f"/pods/{namespace}/{pod_name}")
    summary = _pod_summary_from_payload(payload)
    status = _mapping_value(payload, "status") or {}
    return RancherPodDetail(
        id=summary.id,
        name=summary.name,
        namespace=summary.namespace,
        phase=summary.phase,
        ready=summary.ready,
        ready_containers=summary.ready_containers,
        total_containers=summary.total_containers,
        restart_count=summary.restart_count,
        pod_ip=summary.pod_ip,
        node_name=summary.node_name,
        qos_class=summary.qos_class,
        owner_kind=summary.owner_kind,
        owner_name=summary.owner_name,
        host_ip=_string_value(status, "hostIP"),
        service_account_name=_string_value(
            _mapping_value(payload, "spec"),
            "serviceAccountName",
        ),
        link_keys=sorted(_mapping_value(payload, "links") or {}),
        conditions=_conditions_from_status(status),
        containers=_container_summaries(status),
        payload=dict(payload),
    )


async def rancher_pod_get(
    namespace: str,
    pod_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> RancherPodDetail:
    """Fetch one pod by namespace and name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_pod_get(instance_name, cluster_id, namespace, pod_name, client)
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as steve_client:
        return await _fetch_pod_get(instance_name, cluster_id, namespace, pod_name, steve_client)


async def rancher_pods_list_tool(
    namespace: str,
    cluster_id: str = "local",
    phase: str | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
) -> RancherPodList:
    """Public MCP wrapper for curated pod list."""

    return await rancher_pods_list(
        namespace=namespace,
        cluster_id=cluster_id,
        phase=phase,
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
        instance=instance,
    )


async def rancher_pod_get_tool(
    namespace: str,
    pod_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherPodDetail:
    """Public MCP wrapper for curated pod detail."""

    return await rancher_pod_get(
        namespace=namespace,
        pod_name=pod_name,
        cluster_id=cluster_id,
        instance=instance,
    )
