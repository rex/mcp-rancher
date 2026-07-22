"""Catalog and profile discovery tools."""

from __future__ import annotations

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
    """List every Rancher instance this deployment knows about, each with its base
    URL and target version, so an agent can pick a valid `instance` argument before
    calling any other tool."""

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
    """Report the capability catalog's resource domains — RBAC, storage, networking,
    logging, and so on — with plane and resource counts per domain, useful for
    orienting before drilling into one area."""

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
    """Return static deployment metadata for one Rancher instance: its configured URL,
    primary target version, and compatibility floor, without making a network call."""

    resolved_settings = settings or get_settings()
    resolved_catalog = catalog or get_capability_catalog(resolved_settings.catalog_path)
    return build_server_profile(
        settings=resolved_settings,
        primary_target_version=resolved_catalog.primary_target.version,
    )
