"""Shared schema and resource loaders for generic Rancher resource tools."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from rancher_mcp.clients.management import ManagementDiscoveryClient
from rancher_mcp.clients.steve import SteveDiscoveryClient
from rancher_mcp.exceptions import (
    RancherCapabilityError,
    RancherInvalidArgumentError,
    RancherNotFoundError,
)
from rancher_mcp.identifiers import require_safe_identifier
from rancher_mcp.models.resources import GenericResourceItem
from rancher_mcp.services.resources.builders_item import build_resource_item
from rancher_mcp.services.resources.paths import build_resource_path, schema_path
from rancher_mcp.services.resources.schema import (
    ResourceSchemaReference,
    schema_reference_from_payload,
)
from rancher_mcp.services.safety import require_consistent_namespace


@dataclass(frozen=True)
class ResourceContext:
    """Resolved schema, resource path, payload, and normalized resource item."""

    schema: ResourceSchemaReference
    resource_path: str
    resource_payload: dict[str, object]
    resource: GenericResourceItem


async def _get_schema_json(
    client: ManagementDiscoveryClient | SteveDiscoveryClient,
    path: str,
    schema_id: str,
) -> dict[str, object]:
    """Fetch a schema payload, mapping a 404 to a clean capability error.

    When an optional app / CRD is not installed, Rancher 404s the schema
    lookup. Surfacing that as a bare NOT_FOUND leaves the agent to
    prose-sniff a raw "page not found"; instead raise a uniform
    CAPABILITY_ERROR so it can branch cleanly (ROADMAP K-8a). The curated
    per-tool equivalent is K-8b.
    """

    try:
        return await client.get_json(path)
    except RancherNotFoundError as exc:
        raise RancherCapabilityError(
            f"capability not available: schema {schema_id!r} is not installed "
            "on this cluster (the resource type does not exist here)."
        ) from exc


def _require_one_resource(payload: Mapping[str, object]) -> None:
    """Refuse a reply that is a collection where one resource was asked for.

    The path builder no longer returns a collection path for a resource id.
    This is what still holds if something else ever does: a mutation built on
    a collection's reply acts on everything in it.
    """

    if payload.get("type") == "collection":
        raise RancherInvalidArgumentError(
            "`resource_id` named a whole collection, not one resource in it"
        )


async def load_norman_schema_reference(
    schema_id: str,
    client: ManagementDiscoveryClient,
) -> ResourceSchemaReference:
    """Load and normalize one Norman schema reference."""

    schema_payload = await _get_schema_json(
        client, schema_path("/v3/schemas", schema_id), schema_id
    )
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

    require_safe_identifier("resource_id", resource_id, single_segment=True)
    schema = await load_norman_schema_reference(schema_id, client)
    resource_path = build_resource_path(schema, resource_id=resource_id)
    resource_payload = await client.get_json(resource_path)
    _require_one_resource(resource_payload)
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

    schema_payload = await _get_schema_json(client, schema_path("/schemas", schema_id), schema_id)
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
    """Load one Steve resource and its schema-derived path context.

    ``namespace`` is checked before anything is fetched: it must be one plain
    name, and it must not contradict the namespace ``resource_id`` already
    carries — that one is what the request uses, so a different ``namespace``
    could only mislead whoever reads the call, the prompt or the audit record.
    """

    if namespace is not None:
        require_safe_identifier("namespace", namespace, single_segment=True)
    require_safe_identifier("resource_id", resource_id)
    require_consistent_namespace(namespace, resource_id)
    schema = await load_steve_schema_reference(cluster_id, schema_id, steve_client)
    if namespace is not None and not schema.namespaced:
        raise RancherInvalidArgumentError(
            f"`namespace` was given, but {schema_id} is cluster-scoped: the request would "
            "ignore it. Leave it out."
        )
    resource_path = build_resource_path(
        schema,
        resource_id=resource_id,
        namespace=namespace,
    )
    resource_payload = await steve_client.get_json(resource_path)
    _require_one_resource(resource_payload)
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
