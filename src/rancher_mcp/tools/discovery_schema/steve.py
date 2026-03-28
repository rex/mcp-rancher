# pyright: reportPrivateUsage=false
"""Steve schema discovery tools."""

from __future__ import annotations

from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.discovery import SchemaDetail, SchemaList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.discovery_schema.shared import (
    _schema_detail_from_payload,
    _schema_payloads,
    _schema_summary_from_payload,
)


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
