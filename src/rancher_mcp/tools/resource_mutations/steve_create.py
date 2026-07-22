"""Steve generic resource create implementation."""

from __future__ import annotations

from rancher_mcp.audit import audit_mutation
from rancher_mcp.clients.management import ManagementMutationClient, RancherManagementClient
from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceMutationResult
from rancher_mcp.rate_limit import rate_limit_writes
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import parse_query_params
from rancher_mcp.services.resources import (
    build_k8s_proxy_collection_path,
    build_resource_mutation_result,
)
from rancher_mcp.services.resources.capabilities import (
    ensure_create_supported,
    restrict_payload_fields,
)
from rancher_mcp.services.resources.contexts import load_steve_schema_reference
from rancher_mcp.services.resources.schema import parse_required_payload_object
from rancher_mcp.services.safety import ensure_instance_writable


async def _create_steve_resource(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    schema_id: str,
    payload_json: str,
    params_json: str | None,
    steve_client: SteveDiscoveryClient,
    management_client: ManagementMutationClient,
) -> GenericResourceMutationResult:
    """Create one Steve resource through the schema collection path."""

    schema = await load_steve_schema_reference(cluster_id, schema_id, steve_client)
    ensure_create_supported(schema)
    request_payload = restrict_payload_fields(
        parse_required_payload_object(payload_json),
        schema.creatable_fields,
    )
    request_path = build_k8s_proxy_collection_path(
        schema,
        cluster_id=cluster_id,
        namespace=namespace,
    )
    response_payload = await management_client.post_json(
        request_path,
        payload=request_payload,
        params=parse_query_params(params_json) or None,
    )
    return build_resource_mutation_result(
        instance=instance_name,
        plane="steve",
        schema_id=schema_id,
        operation="create",
        request_method="POST",
        request_path=request_path,
        payload=response_payload,
        cluster_id=cluster_id,
        namespace=namespace,
    )


@audit_mutation(operation="create", plane="steve")
@rate_limit_writes
async def rancher_steve_resource_create(
    schema_id: str,
    payload_json: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    params_json: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    steve_client: SteveDiscoveryClient | None = None,
    management_client: ManagementMutationClient | None = None,
) -> GenericResourceMutationResult:
    """Create one Steve resource by schema type."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    ensure_instance_writable(instance_name, instance_config)
    if steve_client is not None and management_client is not None:
        return await _create_steve_resource(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            payload_json,
            params_json,
            steve_client,
            management_client,
        )
    async with (
        RancherManagementClient(instance_name, instance_config) as managed_client,
        RancherSteveClient(
            instance_name,
            instance_config,
            cluster_id=cluster_id,
        ) as proxy_client,
    ):
        return await _create_steve_resource(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            payload_json,
            params_json,
            proxy_client,
            managed_client,
        )


async def rancher_steve_resource_create_tool(
    schema_id: str,
    payload_json: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    params_json: str | None = None,
    instance: str | None = None,
) -> GenericResourceMutationResult:
    """Create a new Steve Kubernetes-proxy resource from a raw JSON payload under any
    schema id and return the resulting object — the untyped escape hatch when no
    curated create tool exists for that kind."""

    return await rancher_steve_resource_create(
        schema_id=schema_id,
        payload_json=payload_json,
        cluster_id=cluster_id,
        namespace=namespace,
        params_json=params_json,
        instance=instance,
    )
