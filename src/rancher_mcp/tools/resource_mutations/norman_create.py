"""Norman generic resource create implementation."""

from __future__ import annotations

from rancher_mcp.audit import audit_mutation
from rancher_mcp.clients.management import ManagementMutationClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceMutationResult
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import parse_query_params
from rancher_mcp.services.resources import build_collection_path, build_resource_mutation_result
from rancher_mcp.services.resources.capabilities import (
    ensure_create_supported,
    restrict_payload_fields,
)
from rancher_mcp.services.resources.contexts import load_norman_schema_reference
from rancher_mcp.services.resources.schema import parse_required_payload_object
from rancher_mcp.services.safety import ensure_instance_writable


async def _create_norman_resource(
    instance_name: str,
    schema_id: str,
    payload_json: str,
    params_json: str | None,
    client: ManagementMutationClient,
) -> GenericResourceMutationResult:
    """Create one Norman resource through the schema collection path."""

    schema = await load_norman_schema_reference(schema_id, client)
    ensure_create_supported(schema)
    request_payload = restrict_payload_fields(
        parse_required_payload_object(payload_json),
        schema.creatable_fields,
    )
    request_path = build_collection_path(schema)
    response_payload = await client.post_json(
        request_path,
        payload=request_payload,
        params=parse_query_params(params_json) or None,
    )
    return build_resource_mutation_result(
        instance=instance_name,
        plane="norman",
        schema_id=schema_id,
        operation="create",
        request_method="POST",
        request_path=request_path,
        payload=response_payload,
    )


@audit_mutation(operation="create", plane="norman")
async def rancher_norman_resource_create(
    schema_id: str,
    payload_json: str,
    params_json: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementMutationClient | None = None,
) -> GenericResourceMutationResult:
    """Create one Norman resource by schema type."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    ensure_instance_writable(instance_name, instance_config)
    if client is not None:
        return await _create_norman_resource(
            instance_name,
            schema_id,
            payload_json,
            params_json,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _create_norman_resource(
            instance_name,
            schema_id,
            payload_json,
            params_json,
            managed_client,
        )


async def rancher_norman_resource_create_tool(
    schema_id: str,
    payload_json: str,
    params_json: str | None = None,
    instance: str | None = None,
) -> GenericResourceMutationResult:
    """Public MCP wrapper for Norman generic create."""

    return await rancher_norman_resource_create(
        schema_id=schema_id,
        payload_json=payload_json,
        params_json=params_json,
        instance=instance,
    )
