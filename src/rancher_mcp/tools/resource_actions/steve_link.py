"""Steve generic resource link-follow implementation."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceLinkResult
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resources import build_resource_link_result, resolve_resource_link_path
from rancher_mcp.tools.resource_actions.steve_common import load_steve_resource_context


async def _fetch_steve_resource_link_follow(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    schema_id: str,
    resource_id: str,
    link_name: str,
    steve_client: SteveDiscoveryClient,
    management_client: ManagementDiscoveryClient,
) -> GenericResourceLinkResult:
    """Follow a Steve resource link."""

    context = await load_steve_resource_context(
        cluster_id=cluster_id,
        namespace=namespace,
        schema_id=schema_id,
        resource_id=resource_id,
        steve_client=steve_client,
    )
    link_path = resolve_resource_link_path(
        link_name=link_name,
        payload=context.resource_payload,
    )
    response_payload = await management_client.get_json(link_path)
    return build_resource_link_result(
        instance=instance_name,
        plane="steve",
        schema_id=schema_id,
        resource_id=context.resource.id or resource_id,
        link_name=link_name,
        cluster_id=cluster_id,
        namespace=context.resource.namespace or namespace,
        link_path=link_path,
        payload=response_payload,
    )


async def rancher_steve_resource_link_follow(
    schema_id: str,
    resource_id: str,
    link_name: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    steve_client: SteveDiscoveryClient | None = None,
    management_client: ManagementDiscoveryClient | None = None,
) -> GenericResourceLinkResult:
    """Follow a Steve resource link by resource type and id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if steve_client is not None and management_client is not None:
        return await _fetch_steve_resource_link_follow(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            resource_id,
            link_name,
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
        return await _fetch_steve_resource_link_follow(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            resource_id,
            link_name,
            proxy_client,
            managed_client,
        )


async def rancher_steve_resource_link_follow_tool(
    schema_id: str,
    resource_id: str,
    link_name: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    instance: str | None = None,
) -> GenericResourceLinkResult:
    """Public MCP wrapper for Steve generic link follow."""

    return await rancher_steve_resource_link_follow(
        schema_id=schema_id,
        resource_id=resource_id,
        link_name=link_name,
        cluster_id=cluster_id,
        namespace=namespace,
        instance=instance,
    )
