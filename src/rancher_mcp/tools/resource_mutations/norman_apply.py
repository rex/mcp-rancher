"""Norman generic resource apply implementation."""

from __future__ import annotations

from rancher_mcp.audit import audit_mutation
from rancher_mcp.clients.management import ManagementMutationClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceMutationResult
from rancher_mcp.rate_limit import rate_limit_writes
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import parse_query_params
from rancher_mcp.services.resources import build_resource_mutation_result
from rancher_mcp.services.resources.capabilities import (
    ensure_apply_supported,
    restrict_payload_fields,
)
from rancher_mcp.services.resources.contexts import load_norman_resource_context
from rancher_mcp.services.resources.schema import parse_required_payload_object
from rancher_mcp.services.safety import ensure_instance_writable


async def _apply_norman_resource(
    instance_name: str,
    schema_id: str,
    resource_id: str,
    payload_json: str,
    params_json: str | None,
    client: ManagementMutationClient,
) -> GenericResourceMutationResult:
    """Update one Norman resource via its resource PUT path."""

    context = await load_norman_resource_context(schema_id, resource_id, client)
    ensure_apply_supported(context.schema)
    request_payload = restrict_payload_fields(
        parse_required_payload_object(payload_json),
        context.schema.updatable_fields,
    )
    response_payload = await client.put_json(
        context.resource_path,
        payload=request_payload,
        params=parse_query_params(params_json) or None,
    )
    return build_resource_mutation_result(
        instance=instance_name,
        plane="norman",
        schema_id=schema_id,
        operation="apply",
        request_method="PUT",
        request_path=context.resource_path,
        payload=response_payload,
        resource_id_hint=context.resource.id or resource_id,
        resource_path_hint=context.resource_path,
    )


@audit_mutation(operation="apply", plane="norman")
@rate_limit_writes
async def rancher_norman_resource_apply(
    schema_id: str,
    resource_id: str,
    payload_json: str,
    params_json: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementMutationClient | None = None,
) -> GenericResourceMutationResult:
    """Apply one Norman resource by schema type and id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    ensure_instance_writable(instance_name, instance_config)
    if client is not None:
        return await _apply_norman_resource(
            instance_name,
            schema_id,
            resource_id,
            payload_json,
            params_json,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _apply_norman_resource(
            instance_name,
            schema_id,
            resource_id,
            payload_json,
            params_json,
            managed_client,
        )


async def rancher_norman_resource_apply_tool(
    schema_id: str,
    resource_id: str,
    payload_json: str,
    params_json: str | None = None,
    instance: str | None = None,
) -> GenericResourceMutationResult:
    """Replace one Norman resource's full body via PUT under any schema id and
    return the updated object — the untyped escape hatch for updates no curated
    apply tool yet covers."""

    return await rancher_norman_resource_apply(
        schema_id=schema_id,
        resource_id=resource_id,
        payload_json=payload_json,
        params_json=params_json,
        instance=instance,
    )
