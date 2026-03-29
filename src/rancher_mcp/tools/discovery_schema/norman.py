"""Norman schema discovery tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.discovery import SchemaDetail, SchemaList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.discovery_schema.shared import (
    schema_detail_from_payload,
    schema_payloads,
    schema_summary_from_payload,
)


async def _fetch_norman_schema_list(
    instance_name: str,
    client: ManagementDiscoveryClient,
) -> SchemaList:
    """Fetch Norman schema inventory."""

    payload = await client.get_json("/v3/schemas")
    schemas = [schema_summary_from_payload(item) for item in schema_payloads(payload.get("data"))]
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
    return schema_detail_from_payload(instance=instance_name, plane="norman", payload=payload)


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


async def rancher_norman_schema_list_tool(instance: str | None = None) -> SchemaList:
    """Public MCP wrapper for Norman schema inventory."""

    return await rancher_norman_schema_list(instance=instance)


async def rancher_norman_schema_get_tool(
    schema_id: str,
    instance: str | None = None,
) -> SchemaDetail:
    """Public MCP wrapper for Norman schema detail."""

    return await rancher_norman_schema_get(schema_id, instance=instance)
