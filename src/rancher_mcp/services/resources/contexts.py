"""Shared schema and resource loaders for generic Rancher resource tools."""

from __future__ import annotations

from dataclasses import dataclass

from rancher_mcp.clients.management import ManagementDiscoveryClient
from rancher_mcp.clients.steve import SteveDiscoveryClient
from rancher_mcp.models.resources import GenericResourceItem
from rancher_mcp.services.resources.builders_item import build_resource_item
from rancher_mcp.services.resources.paths import build_resource_path
from rancher_mcp.services.resources.schema import (
    ResourceSchemaReference,
    schema_reference_from_payload,
)


@dataclass(frozen=True)
class ResourceContext:
    """Resolved schema, resource path, payload, and normalized resource item."""

    schema: ResourceSchemaReference
    resource_path: str
    resource_payload: dict[str, object]
    resource: GenericResourceItem


async def load_norman_schema_reference(
    schema_id: str,
    client: ManagementDiscoveryClient,
) -> ResourceSchemaReference:
    """Load and normalize one Norman schema reference."""

    schema_payload = await client.get_json(f"/v3/schemas/{schema_id}")
    return schema_reference_from_payload(
        plane="norman",
        cluster_id=None,
        schema_id=schema_id,
        payload=schema_payload,
    )


async def load_norman_resource_context(
    schema_id: str,
    resource_id: str,
    client: ManagementDiscoveryClient,
) -> ResourceContext:
    """Load one Norman resource and its schema-derived path context."""

    schema = await load_norman_schema_reference(schema_id, client)
    resource_path = build_resource_path(schema, resource_id=resource_id)
    resource_payload = await client.get_json(resource_path)
    resource = build_resource_item(
        plane="norman",
        cluster_id=None,
        payload=resource_payload,
    )
    return ResourceContext(
        schema=schema,
        resource_path=resource_path,
        resource_payload=dict(resource_payload),
        resource=resource,
    )


async def load_steve_schema_reference(
    cluster_id: str,
    schema_id: str,
    client: SteveDiscoveryClient,
) -> ResourceSchemaReference:
    """Load and normalize one Steve schema reference."""

    schema_payload = await client.get_json(f"/schemas/{schema_id}")
    return schema_reference_from_payload(
        plane="steve",
        cluster_id=cluster_id,
        schema_id=schema_id,
        payload=schema_payload,
    )


async def load_steve_resource_context(
    *,
    cluster_id: str,
    namespace: str | None,
    schema_id: str,
    resource_id: str,
    steve_client: SteveDiscoveryClient,
) -> ResourceContext:
    """Load one Steve resource and its schema-derived path context."""

    schema = await load_steve_schema_reference(cluster_id, schema_id, steve_client)
    resource_path = build_resource_path(
        schema,
        resource_id=resource_id,
        namespace=namespace,
    )
    resource_payload = await steve_client.get_json(resource_path)
    resource = build_resource_item(
        plane="steve",
        cluster_id=cluster_id,
        payload=resource_payload,
    )
    return ResourceContext(
        schema=schema,
        resource_path=resource_path,
        resource_payload=dict(resource_payload),
        resource=resource,
    )
