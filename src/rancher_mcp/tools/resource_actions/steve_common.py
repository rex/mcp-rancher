"""Shared Steve resource-loading helpers for generic action/link tools."""

from __future__ import annotations

from dataclasses import dataclass

from rancher_mcp.clients.steve import SteveDiscoveryClient
from rancher_mcp.models.resources import GenericResourceItem
from rancher_mcp.services.resources import (
    build_resource_item,
    build_resource_path,
    schema_reference_from_payload,
)


@dataclass(frozen=True)
class SteveResourceContext:
    """Resolved Steve schema, resource path, payload, and normalized resource item."""

    schema_id: str
    resource_path: str
    resource_payload: dict[str, object]
    resource: GenericResourceItem


async def load_steve_resource_context(
    *,
    cluster_id: str,
    namespace: str | None,
    schema_id: str,
    resource_id: str,
    steve_client: SteveDiscoveryClient,
) -> SteveResourceContext:
    """Resolve the Steve schema and load one concrete resource payload."""

    schema_payload = await steve_client.get_json(f"/schemas/{schema_id}")
    schema = schema_reference_from_payload(
        plane="steve",
        cluster_id=cluster_id,
        schema_id=schema_id,
        payload=schema_payload,
    )
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
    return SteveResourceContext(
        schema_id=schema_id,
        resource_path=resource_path,
        resource_payload=dict(resource_payload),
        resource=resource,
    )
