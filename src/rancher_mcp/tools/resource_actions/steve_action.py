"""Steve generic resource action implementation."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceActionResult
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resources import (
    build_resource_action_result,
    parse_payload_object,
    resolve_resource_action_path,
)
from rancher_mcp.tools.resource_actions.steve_common import load_steve_resource_context


async def _fetch_steve_resource_action_invoke(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    schema_id: str,
    resource_id: str,
    action_name: str,
    payload_json: str | None,
    steve_client: SteveDiscoveryClient,
    management_client: ManagementDiscoveryClient,
) -> GenericResourceActionResult:
    """Invoke a Steve resource action."""

    context = await load_steve_resource_context(
        cluster_id=cluster_id,
        namespace=namespace,
        schema_id=schema_id,
        resource_id=resource_id,
        steve_client=steve_client,
    )
    action_path = resolve_resource_action_path(
        action_name=action_name,
        payload=context.resource_payload,
    )
    response_payload = await management_client.post_json(
        action_path,
        payload=parse_payload_object(payload_json),
    )
    return build_resource_action_result(
        instance=instance_name,
        plane="steve",
        schema_id=schema_id,
        resource_id=context.resource.id or resource_id,
        action_name=action_name,
        cluster_id=cluster_id,
        namespace=context.resource.namespace or namespace,
        action_path=action_path,
        payload=response_payload,
    )


async def rancher_steve_resource_action_invoke(
    schema_id: str,
    resource_id: str,
    action_name: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    payload_json: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    steve_client: SteveDiscoveryClient | None = None,
    management_client: ManagementDiscoveryClient | None = None,
) -> GenericResourceActionResult:
    """Invoke a Steve resource action by resource type and id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if steve_client is not None and management_client is not None:
        return await _fetch_steve_resource_action_invoke(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            resource_id,
            action_name,
            payload_json,
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
        return await _fetch_steve_resource_action_invoke(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            resource_id,
            action_name,
            payload_json,
            proxy_client,
            managed_client,
        )


async def rancher_steve_resource_action_invoke_tool(
    schema_id: str,
    resource_id: str,
    action_name: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    payload_json: str | None = None,
    instance: str | None = None,
) -> GenericResourceActionResult:
    """Public MCP wrapper for Steve generic action invocation."""

    return await rancher_steve_resource_action_invoke(
        schema_id=schema_id,
        resource_id=resource_id,
        action_name=action_name,
        cluster_id=cluster_id,
        namespace=namespace,
        payload_json=payload_json,
        instance=instance,
    )
