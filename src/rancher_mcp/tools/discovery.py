"""Discovery tools and helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mcp.server.fastmcp import FastMCP

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.discovery import (
    APIPlaneList,
    APIPlaneSummary,
    CapabilityCatalog,
    CapabilityDomainList,
    CapabilityDomainSummary,
    InstanceList,
    SchemaDetail,
    SchemaList,
    SchemaSummary,
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


def _mapping_keys(payload: object) -> list[str]:
    """Return sorted keys from a mapping-like payload."""

    if not isinstance(payload, Mapping):
        return []
    return sorted(cast(Mapping[str, object], payload).keys())


def _api_version_string(payload: object) -> str | None:
    """Return a compact API version string from a Rancher root payload field."""

    if isinstance(payload, str):
        return payload
    if not isinstance(payload, Mapping):
        return None

    mapping = cast(Mapping[str, object], payload)
    raw_group = mapping.get("group")
    group = raw_group if isinstance(raw_group, str) else None
    raw_version = mapping.get("version")
    version = raw_version if isinstance(raw_version, str) else None

    if group and version:
        return f"{group}/{version}"
    return version or group


def _string_list(payload: object) -> list[str]:
    """Normalize a loose list payload into a strict string list."""

    if not isinstance(payload, list):
        return []
    items = cast(list[object], payload)
    return [str(item) for item in items]


def _schema_payloads(raw_items: object) -> list[Mapping[str, object]]:
    """Filter Rancher collection payloads down to schema mappings."""

    if not isinstance(raw_items, list):
        return []

    items = cast(list[object], raw_items)
    payloads: list[Mapping[str, object]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        mapping = cast(Mapping[str, object], item)
        if isinstance(mapping.get("id"), str):
            payloads.append(mapping)
    return payloads


def _schema_summary_from_payload(payload: Mapping[str, object]) -> SchemaSummary:
    """Normalize a Norman or Steve schema payload into a compact summary."""

    raw_plural_name = payload.get("pluralName")
    plural_name = raw_plural_name if isinstance(raw_plural_name, str) else None
    collection_methods = _string_list(payload.get("collectionMethods"))
    resource_methods = _string_list(payload.get("resourceMethods"))
    field_count = len(_mapping_keys(payload.get("resourceFields")))
    raw_id = payload.get("id")
    schema_id = raw_id if isinstance(raw_id, str) else ""
    return SchemaSummary(
        id=schema_id,
        plural_name=plural_name,
        collection_methods=collection_methods,
        resource_methods=resource_methods,
        link_keys=_mapping_keys(payload.get("links")),
        field_count=field_count,
    )


def _schema_detail_from_payload(
    *,
    instance: str,
    plane: str,
    payload: Mapping[str, object],
    cluster_id: str | None = None,
) -> SchemaDetail:
    """Normalize a Norman or Steve schema payload into detailed output."""

    summary = _schema_summary_from_payload(payload)
    return SchemaDetail(
        instance=instance,
        plane=plane,
        cluster_id=cluster_id,
        id=summary.id,
        plural_name=summary.plural_name,
        collection_methods=summary.collection_methods,
        resource_methods=summary.resource_methods,
        link_keys=summary.link_keys,
        field_keys=_mapping_keys(payload.get("resourceFields")),
        collection_filter_keys=_mapping_keys(payload.get("collectionFilters")),
    )


async def _fetch_api_plane_list(
    instance_name: str,
    management_client: ManagementDiscoveryClient,
    steve_client: SteveDiscoveryClient,
    cluster_id: str,
) -> APIPlaneList:
    """Fetch the available API planes for an instance."""

    norman_root = await management_client.get_json("/v3")
    steve_root = await steve_client.get_json("/")
    planes = [
        APIPlaneSummary(
            id="norman",
            name="Rancher Norman management API",
            root_path="/v3",
            api_version=_api_version_string(norman_root.get("apiVersion")),
            link_count=len(_mapping_keys(norman_root.get("links"))),
        ),
        APIPlaneSummary(
            id="steve",
            name="Rancher Steve Kubernetes proxy API",
            root_path="/v1" if cluster_id == "local" else f"/k8s/clusters/{cluster_id}/v1",
            api_version=_api_version_string(steve_root.get("apiVersion")),
            cluster_id=cluster_id,
            link_count=len(_mapping_keys(steve_root.get("links"))),
        ),
    ]
    return APIPlaneList(instance=instance_name, cluster_id=cluster_id, planes=planes)


async def rancher_api_plane_list(
    instance: str | None = None,
    cluster_id: str = "local",
    settings: AppSettings | None = None,
    management_client: ManagementDiscoveryClient | None = None,
    steve_client: SteveDiscoveryClient | None = None,
) -> APIPlaneList:
    """List available Rancher API planes for an instance."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if management_client is not None and steve_client is not None:
        return await _fetch_api_plane_list(
            instance_name,
            management_client,
            steve_client,
            cluster_id,
        )
    async with (
        RancherManagementClient(instance_name, instance_config) as norman_client,
        RancherSteveClient(
            instance_name,
            instance_config,
            cluster_id=cluster_id,
        ) as proxy_client,
    ):
        return await _fetch_api_plane_list(
            instance_name,
            norman_client,
            proxy_client,
            cluster_id,
        )


async def _fetch_norman_schema_list(
    instance_name: str,
    client: ManagementDiscoveryClient,
) -> SchemaList:
    """Fetch Norman schema inventory."""

    payload = await client.get_json("/v3/schemas")
    schemas = [_schema_summary_from_payload(item) for item in _schema_payloads(payload.get("data"))]
    return SchemaList(
        instance=instance_name,
        plane="norman",
        schema_count=len(schemas),
        schemas=schemas,
    )


async def rancher_norman_schema_list(
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> SchemaList:
    """List Norman schema types exposed by Rancher."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_norman_schema_list(instance_name, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_norman_schema_list(instance_name, managed_client)


async def _fetch_norman_schema_get(
    instance_name: str,
    schema_id: str,
    client: ManagementDiscoveryClient,
) -> SchemaDetail:
    """Fetch one Norman schema by id."""

    payload = await client.get_json(f"/v3/schemas/{schema_id}")
    return _schema_detail_from_payload(instance=instance_name, plane="norman", payload=payload)


async def rancher_norman_schema_get(
    schema_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> SchemaDetail:
    """Fetch detailed Norman schema metadata."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_norman_schema_get(instance_name, schema_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_norman_schema_get(instance_name, schema_id, managed_client)


async def _fetch_steve_schema_list(
    instance_name: str,
    cluster_id: str,
    client: SteveDiscoveryClient,
) -> SchemaList:
    """Fetch Steve schema inventory for a target cluster."""

    payload = await client.get_json("/schemas")
    schemas = [_schema_summary_from_payload(item) for item in _schema_payloads(payload.get("data"))]
    return SchemaList(
        instance=instance_name,
        plane="steve",
        cluster_id=cluster_id,
        schema_count=len(schemas),
        schemas=schemas,
    )


async def rancher_steve_schema_list(
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> SchemaList:
    """List Steve schema types for a target cluster."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_steve_schema_list(instance_name, cluster_id, client)
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as proxy_client:
        return await _fetch_steve_schema_list(instance_name, cluster_id, proxy_client)


async def _fetch_steve_schema_get(
    instance_name: str,
    cluster_id: str,
    schema_id: str,
    client: SteveDiscoveryClient,
) -> SchemaDetail:
    """Fetch one Steve schema by id."""

    payload = await client.get_json(f"/schemas/{schema_id}")
    return _schema_detail_from_payload(
        instance=instance_name,
        plane="steve",
        payload=payload,
        cluster_id=cluster_id,
    )


async def rancher_steve_schema_get(
    schema_id: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> SchemaDetail:
    """Fetch detailed Steve schema metadata for a target cluster."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_steve_schema_get(instance_name, cluster_id, schema_id, client)
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as proxy_client:
        return await _fetch_steve_schema_get(instance_name, cluster_id, schema_id, proxy_client)


async def rancher_api_plane_list_tool(
    instance: str | None = None,
    cluster_id: str = "local",
) -> APIPlaneList:
    """Public MCP wrapper for Rancher API plane discovery."""

    return await rancher_api_plane_list(instance=instance, cluster_id=cluster_id)


async def rancher_norman_schema_list_tool(instance: str | None = None) -> SchemaList:
    """Public MCP wrapper for Norman schema inventory."""

    return await rancher_norman_schema_list(instance=instance)


async def rancher_norman_schema_get_tool(
    schema_id: str,
    instance: str | None = None,
) -> SchemaDetail:
    """Public MCP wrapper for Norman schema detail."""

    return await rancher_norman_schema_get(schema_id, instance=instance)


async def rancher_steve_schema_list_tool(
    cluster_id: str = "local",
    instance: str | None = None,
) -> SchemaList:
    """Public MCP wrapper for Steve schema inventory."""

    return await rancher_steve_schema_list(cluster_id=cluster_id, instance=instance)


async def rancher_steve_schema_get_tool(
    schema_id: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> SchemaDetail:
    """Public MCP wrapper for Steve schema detail."""

    return await rancher_steve_schema_get(
        schema_id,
        cluster_id=cluster_id,
        instance=instance,
    )


def register_discovery_tools(mcp: FastMCP) -> None:
    """Register discovery tools with the FastMCP server."""

    mcp.tool(name="rancher_instance_list")(rancher_instance_list)
    mcp.tool(name="rancher_capability_domain_list")(rancher_capability_domain_list)
    mcp.tool(name="rancher_server_profile_get")(rancher_server_profile_get)
    mcp.tool(name="rancher_server_health")(rancher_server_health_tool)
    mcp.tool(name="rancher_server_version")(rancher_server_version_tool)
    mcp.tool(name="rancher_api_plane_list")(rancher_api_plane_list_tool)
    mcp.tool(name="rancher_norman_schema_list")(rancher_norman_schema_list_tool)
    mcp.tool(name="rancher_norman_schema_get")(rancher_norman_schema_get_tool)
    mcp.tool(name="rancher_steve_schema_list")(rancher_steve_schema_list_tool)
    mcp.tool(name="rancher_steve_schema_get")(rancher_steve_schema_get_tool)
