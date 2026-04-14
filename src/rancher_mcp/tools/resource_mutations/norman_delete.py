"""Norman generic resource delete implementation."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementMutationClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceMutationResult
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import parse_query_params
from rancher_mcp.services.resources import build_resource_mutation_result
from rancher_mcp.services.resources.capabilities import ensure_delete_supported
from rancher_mcp.services.resources.contexts import load_norman_resource_context
from rancher_mcp.services.resources.schema import parse_payload_object
from rancher_mcp.services.safety import (
    ensure_instance_writable,
    require_delete_confirmation,
)


async def _delete_norman_resource(
    instance_name: str,
    schema_id: str,
    resource_id: str,
    confirmation: str,
    payload_json: str | None,
    params_json: str | None,
    client: ManagementMutationClient,
) -> GenericResourceMutationResult:
    """Delete one Norman resource by schema type and id."""

    require_delete_confirmation(
        plane="norman",
        schema_id=schema_id,
        resource_id=resource_id,
        confirmation=confirmation,
    )
    context = await load_norman_resource_context(schema_id, resource_id, client)
    ensure_delete_supported(context.schema)
    delete_payload = parse_payload_object(payload_json) if payload_json is not None else None
    response_payload = await client.delete_json(
        context.resource_path,
        payload=delete_payload or None,
        params=parse_query_params(params_json) or None,
    )
    return build_resource_mutation_result(
        instance=instance_name,
        plane="norman",
        schema_id=schema_id,
        operation="delete",
        request_method="DELETE",
        request_path=context.resource_path,
        payload=response_payload,
        resource_id_hint=context.resource.id or resource_id,
        resource_path_hint=context.resource_path,
    )


async def rancher_norman_resource_delete(
    schema_id: str,
    resource_id: str,
    confirmation: str,
    payload_json: str | None = None,
    params_json: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementMutationClient | None = None,
) -> GenericResourceMutationResult:
    """Delete one Norman resource by schema type and id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    ensure_instance_writable(instance_name, instance_config)
    if client is not None:
        return await _delete_norman_resource(
            instance_name,
            schema_id,
            resource_id,
            confirmation,
            payload_json,
            params_json,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _delete_norman_resource(
            instance_name,
            schema_id,
            resource_id,
            confirmation,
            payload_json,
            params_json,
            managed_client,
        )


async def rancher_norman_resource_delete_tool(
    schema_id: str,
    resource_id: str,
    confirmation: str,
    payload_json: str | None = None,
    params_json: str | None = None,
    instance: str | None = None,
) -> GenericResourceMutationResult:
    """Public MCP wrapper for Norman generic delete."""

    return await rancher_norman_resource_delete(
        schema_id=schema_id,
        resource_id=resource_id,
        confirmation=confirmation,
        payload_json=payload_json,
        params_json=params_json,
        instance=instance,
    )
