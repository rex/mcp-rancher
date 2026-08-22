"""Catalog and profile discovery tools.

The ``*_tool`` wrappers at the bottom are the PUBLIC MCP surface. The functions
above them keep ``settings``/``catalog`` parameters purely as a dependency-
injection seam for tests, and those must never reach the wire — see the wrappers'
shared note for what happened when they did.
"""

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


# ---------------------------------------------------------------------------
# Public MCP wrappers.
#
# These three tools were registered directly against the implementations above,
# so FastMCP derived their input schemas from the DI parameters and published
# `settings` and `catalog` as ordinary, model-callable arguments. Two things
# followed, both verified before this fix:
#
#   1. A caller could pass its own `settings` object and have it honoured — the
#      returned instance list would carry a caller-supplied URL and
#      `readOnly: false`. The token was never echoed (the redaction layer held)
#      and all three tools are read-only, so this was not credential exfil or a
#      write path; it was a model-deception vector, since an agent would believe
#      a fabricated instance it had been handed.
#   2. Inlining `AppSettings` into the schema published our environment-variable
#      names — including `RANCHER_TOKEN`, `RANCHER_URL`, `RANCHER_CA_BUNDLE` — to
#      every client, and cost 14.7 KB of context across the three tools for
#      parameters no caller should ever set.
#
# Every generated tool in this repo already goes through a `*_tool` wrapper for
# exactly this reason. These were the three that predated the convention.
# `test_no_tool_exposes_internal_plumbing` now enforces it fleet-wide.
# ---------------------------------------------------------------------------


async def rancher_instance_list_tool() -> InstanceList:
    """List every Rancher instance this deployment knows about, each with its base
    URL and target version, so an agent can pick a valid `instance` argument before
    calling any other tool."""

    return await rancher_instance_list()


async def rancher_capability_domain_list_tool() -> CapabilityDomainList:
    """Report the capability catalog's resource domains — RBAC, storage, networking,
    logging, and so on — with plane and resource counts per domain, useful for
    orienting before drilling into one area."""

    return await rancher_capability_domain_list()


async def rancher_server_profile_get_tool() -> ServerProfile:
    """Return static deployment metadata for one Rancher instance: its configured URL,
    primary target version, and compatibility floor, without making a network call."""

    return await rancher_server_profile_get()
