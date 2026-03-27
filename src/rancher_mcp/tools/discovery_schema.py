"""API-plane and schema discovery tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.discovery import (
    APIPlaneList,
    APIPlaneSummary,
    SchemaDetail,
    SchemaList,
    SchemaSummary,
)
from rancher_mcp.services.instances import resolve_instance


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
