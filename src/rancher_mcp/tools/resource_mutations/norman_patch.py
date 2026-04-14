"""Norman generic resource patch implementation."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementMutationClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceMutationResult
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import parse_query_params
from rancher_mcp.services.resources import build_resource_mutation_result
from rancher_mcp.services.resources.capabilities import (
    ensure_patch_supported,
    merge_patch_object,
    restrict_payload_fields,
)
from rancher_mcp.services.resources.contexts import load_norman_resource_context
from rancher_mcp.services.resources.schema import parse_required_payload_object
from rancher_mcp.services.safety import ensure_instance_writable


async def _patch_norman_resource(
    instance_name: str,
    schema_id: str,
    resource_id: str,
    payload_json: str,
    params_json: str | None,
    client: ManagementMutationClient,
) -> GenericResourceMutationResult:
    """Patch one Norman resource by merging into a schema-filtered PUT body."""

    context = await load_norman_resource_context(schema_id, resource_id, client)
    ensure_patch_supported(context.schema)
    patch_payload = restrict_payload_fields(
        parse_required_payload_object(payload_json),
        context.schema.updatable_fields,
    )
    mutable_payload = (
        {
            key: value
            for key, value in context.resource_payload.items()
            if key in context.schema.updatable_fields
        }
        if context.schema.updatable_fields
        else {}
    )
    response_payload = await client.put_json(
        context.resource_path,
        payload=merge_patch_object(mutable_payload, patch_payload),
        params=parse_query_params(params_json) or None,
    )
    return build_resource_mutation_result(
        instance=instance_name,
        plane="norman",
        schema_id=schema_id,
        operation="patch",
        request_method="PUT",
        request_path=context.resource_path,
        payload=response_payload,
        resource_id_hint=context.resource.id or resource_id,
        resource_path_hint=context.resource_path,
    )


async def rancher_norman_resource_patch(
    schema_id: str,
    resource_id: str,
    payload_json: str,
    params_json: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementMutationClient | None = None,
) -> GenericResourceMutationResult:
    """Patch one Norman resource by schema type and id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    ensure_instance_writable(instance_name, instance_config)
    if client is not None:
        return await _patch_norman_resource(
            instance_name,
            schema_id,
            resource_id,
            payload_json,
            params_json,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _patch_norman_resource(
            instance_name,
            schema_id,
            resource_id,
            payload_json,
            params_json,
            managed_client,
        )


async def rancher_norman_resource_patch_tool(
    schema_id: str,
    resource_id: str,
    payload_json: str,
    params_json: str | None = None,
    instance: str | None = None,
) -> GenericResourceMutationResult:
    """Public MCP wrapper for Norman generic patch."""

    return await rancher_norman_resource_patch(
        schema_id=schema_id,
        resource_id=resource_id,
        payload_json=payload_json,
        params_json=params_json,
        instance=instance,
    )
