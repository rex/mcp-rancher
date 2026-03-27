"""Discovery tools and helpers."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.discovery import (
    CapabilityCatalog,
    CapabilityDomainList,
    CapabilityDomainSummary,
    InstanceList,
    ServerProfile,
)
from rancher_mcp.models.management import ServerHealth, ServerVersion
from rancher_mcp.services.catalog import get_capability_catalog
from rancher_mcp.services.instances import (
    build_instance_list,
    build_server_profile,
    resolve_instance,
)


async def rancher_instance_list(settings: AppSettings | None = None) -> InstanceList:
    """Return the configured Rancher instances."""

    resolved_settings = settings or get_settings()
    catalog = get_capability_catalog(resolved_settings.catalog_path)
    return build_instance_list(
        settings=resolved_settings,
        primary_target_version=catalog.primary_target.version,
    )


async def rancher_capability_domain_list(
    settings: AppSettings | None = None,
    catalog: CapabilityCatalog | None = None,
) -> CapabilityDomainList:
    """Return the catalog's capability domains."""

    resolved_settings = settings or get_settings()
    resolved_catalog = catalog or get_capability_catalog(resolved_settings.catalog_path)
    domains = [
        CapabilityDomainSummary(
            id=domain.id,
            name=domain.name,
            priority=domain.priority,
            plane_count=len(domain.planes),
            resource_count=len(domain.resources),
        )
        for domain in resolved_catalog.domains
    ]
    return CapabilityDomainList(
        schema_version=resolved_catalog.schema_version,
        domain_count=len(domains),
        domains=domains,
    )


async def rancher_server_profile_get(
    settings: AppSettings | None = None,
    catalog: CapabilityCatalog | None = None,
) -> ServerProfile:
    """Return static server profile metadata."""

    resolved_settings = settings or get_settings()
    resolved_catalog = catalog or get_capability_catalog(resolved_settings.catalog_path)
    return build_server_profile(
        settings=resolved_settings,
        primary_target_version=resolved_catalog.primary_target.version,
    )


async def _fetch_server_health(
    instance_name: str,
    client: ManagementDiscoveryClient,
) -> ServerHealth:
    """Fetch Rancher server health using an injected client."""

    message = (await client.get_text("/healthz")).strip() or None
    return ServerHealth(instance=instance_name, healthy=True, message=message)


async def rancher_server_health(
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> ServerHealth:
    """Check the Rancher management server health endpoint."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_server_health(instance_name, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_server_health(instance_name, managed_client)


async def _fetch_server_version(
    instance_name: str,
    client: ManagementDiscoveryClient,
) -> ServerVersion:
    """Fetch Rancher server version using an injected client."""

    payload = await client.get_json("/v3/settings/server-version")
    raw_value = payload.get("value")
    version = raw_value if isinstance(raw_value, str) else None
    return ServerVersion(instance=instance_name, rancher_version=version)


async def rancher_server_version(
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> ServerVersion:
    """Fetch Rancher server version."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_server_version(instance_name, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_server_version(instance_name, managed_client)


async def rancher_server_health_tool(instance: str | None = None) -> ServerHealth:
    """Public MCP wrapper for Rancher server health."""

    return await rancher_server_health(instance=instance)


async def rancher_server_version_tool(instance: str | None = None) -> ServerVersion:
    """Public MCP wrapper for Rancher server version."""

    return await rancher_server_version(instance=instance)


def register_discovery_tools(mcp: FastMCP) -> None:
    """Register discovery tools with the FastMCP server."""

    mcp.tool(name="rancher_instance_list")(rancher_instance_list)
    mcp.tool(name="rancher_capability_domain_list")(rancher_capability_domain_list)
    mcp.tool(name="rancher_server_profile_get")(rancher_server_profile_get)
    mcp.tool(name="rancher_server_health")(rancher_server_health_tool)
    mcp.tool(name="rancher_server_version")(rancher_server_version_tool)
