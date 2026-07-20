"""Find services with no backing endpoints."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.ops.failure_finders import (
    ServicesWithoutEndpointsList,
    ServiceWithoutEndpointsSummary,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.ops.paths import k8s_core_path, k8s_items
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import mapping_value, string_dict, string_value


async def _find_services_without_endpoints(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    client: ManagementDiscoveryClient,
) -> ServicesWithoutEndpointsList:
    """Scan for services with selectors but no backing endpoints.

    One namespace, or the whole cluster when ``namespace`` is None. The
    service<->endpoints correlation is keyed by (namespace, name) so it stays
    correct across namespaces, where service names can collide (ROADMAP K-4).
    """

    svc_path = k8s_core_path(cluster_id, "services", namespace)
    ep_path = k8s_core_path(cluster_id, "endpoints", namespace)
    svc_payload = await client.get_json(svc_path)
    ep_payload = await client.get_json(ep_path)

    ep_with_addresses: set[tuple[str, str]] = set()
    for ep in k8s_items(ep_payload):
        meta = mapping_value(ep, "metadata") or {}
        name = string_value(meta, "name")
        # Fall back to the requested namespace when metadata omits it so
        # single-namespace matching stays name-based (as before); in
        # all-namespaces mode the real payloads always carry it.
        ep_ns = string_value(meta, "namespace") or namespace
        has_addresses = any(
            len(object_items(subset, field="addresses")) > 0
            for subset in object_items(ep, field="subsets")
        )
        if has_addresses and name:
            ep_with_addresses.add((ep_ns or "", name))

    missing: list[ServiceWithoutEndpointsSummary] = []
    for svc in k8s_items(svc_payload):
        meta = mapping_value(svc, "metadata") or {}
        spec = mapping_value(svc, "spec") or {}
        name = string_value(meta, "name") or "<unknown>"
        svc_ns = string_value(meta, "namespace") or namespace
        svc_type = string_value(spec, "type")
        if svc_type == "ExternalName":
            continue
        selector = string_dict(spec.get("selector"))
        if not selector:
            continue
        if (svc_ns or "", name) not in ep_with_addresses:
            missing.append(
                ServiceWithoutEndpointsSummary(
                    name=name,
                    namespace=svc_ns or "<unknown>",
                    service_type=svc_type,
                    selector=selector,
                )
            )

    return ServicesWithoutEndpointsList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        count=len(missing),
        services=missing,
    )


async def rancher_find_services_without_endpoints(
    namespace: str | None = None,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> ServicesWithoutEndpointsList:
    """Find services with selectors but no backing endpoints."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _find_services_without_endpoints(
            instance_name,
            cluster_id,
            namespace,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _find_services_without_endpoints(
            instance_name,
            cluster_id,
            namespace,
            managed_client,
        )


async def rancher_find_services_without_endpoints_tool(
    namespace: str | None = None,
    cluster_id: str = "local",
    instance: str | None = None,
) -> ServicesWithoutEndpointsList:
    """Find services with no backing endpoints -- a fast outage signal.

    Omit `namespace` to scan the whole cluster; pass it to scope to one.
    """

    return await rancher_find_services_without_endpoints(
        namespace=namespace,
        cluster_id=cluster_id,
        instance=instance,
    )
