"""Discovery tools and helpers."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.discovery import (
    CapabilityCatalog,
    CapabilityDomainList,
    CapabilityDomainSummary,
    InstanceList,
    ServerProfile,
)
from rancher_mcp.services.catalog import get_capability_catalog
from rancher_mcp.services.instances import build_instance_list, build_server_profile


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


def register_discovery_tools(mcp: FastMCP) -> None:
    """Register discovery tools with the FastMCP server."""

    mcp.tool(name="rancher_instance_list")(rancher_instance_list)
    mcp.tool(name="rancher_capability_domain_list")(rancher_capability_domain_list)
    mcp.tool(name="rancher_server_profile_get")(rancher_server_profile_get)
