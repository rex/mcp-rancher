"""Generic schema-driven resource action and link tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceActionResult, GenericResourceLinkResult
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resources import (
    build_resource_action_result,
    build_resource_item,
    build_resource_link_result,
    build_resource_path,
    parse_payload_object,
    resolve_resource_action_path,
    resolve_resource_link_path,
    schema_reference_from_payload,
)


async def _fetch_norman_resource_action_invoke(
    instance_name: str,
    schema_id: str,
    resource_id: str,
    action_name: str,
    payload_json: str | None,
    client: ManagementDiscoveryClient,
) -> GenericResourceActionResult:
    """Invoke a Norman resource action."""

    schema_payload = await client.get_json(f"/v3/schemas/{schema_id}")
    schema = schema_reference_from_payload(
        plane="norman",
        cluster_id=None,
        schema_id=schema_id,
        payload=schema_payload,
    )
    resource_path = build_resource_path(schema, resource_id=resource_id)
    resource_payload = await client.get_json(resource_path)
    action_path = resolve_resource_action_path(
        action_name=action_name,
        payload=resource_payload,
    )
    response_payload = await client.post_json(
        action_path,
        payload=parse_payload_object(payload_json),
    )
    resource = build_resource_item(
        plane="norman",
        cluster_id=None,
        payload=resource_payload,
    )
    return build_resource_action_result(
        instance=instance_name,
        plane="norman",
        schema_id=schema_id,
        resource_id=resource.id or resource_id,
        action_name=action_name,
        action_path=action_path,
        payload=response_payload,
    )


async def rancher_norman_resource_action_invoke(
    schema_id: str,
    resource_id: str,
    action_name: str,
    payload_json: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> GenericResourceActionResult:
    """Invoke a Norman resource action by resource type and id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_norman_resource_action_invoke(
            instance_name,
            schema_id,
            resource_id,
            action_name,
            payload_json,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_norman_resource_action_invoke(
            instance_name,
            schema_id,
            resource_id,
            action_name,
            payload_json,
            managed_client,
        )


async def _fetch_norman_resource_link_follow(
    instance_name: str,
    schema_id: str,
    resource_id: str,
    link_name: str,
    client: ManagementDiscoveryClient,
) -> GenericResourceLinkResult:
    """Follow a Norman resource link."""

    schema_payload = await client.get_json(f"/v3/schemas/{schema_id}")
    schema = schema_reference_from_payload(
        plane="norman",
        cluster_id=None,
        schema_id=schema_id,
        payload=schema_payload,
    )
    resource_path = build_resource_path(schema, resource_id=resource_id)
    resource_payload = await client.get_json(resource_path)
    link_path = resolve_resource_link_path(
        link_name=link_name,
        payload=resource_payload,
    )
    response_payload = await client.get_json(link_path)
    resource = build_resource_item(
        plane="norman",
        cluster_id=None,
        payload=resource_payload,
    )
    return build_resource_link_result(
        instance=instance_name,
        plane="norman",
        schema_id=schema_id,
        resource_id=resource.id or resource_id,
        link_name=link_name,
        link_path=link_path,
        payload=response_payload,
    )


async def rancher_norman_resource_link_follow(
    schema_id: str,
    resource_id: str,
    link_name: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> GenericResourceLinkResult:
    """Follow a Norman resource link by resource type and id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_norman_resource_link_follow(
            instance_name,
            schema_id,
            resource_id,
            link_name,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_norman_resource_link_follow(
            instance_name,
            schema_id,
            resource_id,
            link_name,
            managed_client,
        )


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
    action_path = resolve_resource_action_path(
        action_name=action_name,
        payload=resource_payload,
    )
    response_payload = await management_client.post_json(
        action_path,
        payload=parse_payload_object(payload_json),
    )
    resource = build_resource_item(
        plane="steve",
        cluster_id=cluster_id,
        payload=resource_payload,
    )
    return build_resource_action_result(
        instance=instance_name,
        plane="steve",
        schema_id=schema_id,
        resource_id=resource.id or resource_id,
        action_name=action_name,
        cluster_id=cluster_id,
        namespace=resource.namespace or namespace,
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
    link_path = resolve_resource_link_path(
        link_name=link_name,
        payload=resource_payload,
    )
    response_payload = await management_client.get_json(link_path)
    resource = build_resource_item(
        plane="steve",
        cluster_id=cluster_id,
        payload=resource_payload,
    )
    return build_resource_link_result(
        instance=instance_name,
        plane="steve",
        schema_id=schema_id,
        resource_id=resource.id or resource_id,
        link_name=link_name,
        cluster_id=cluster_id,
        namespace=resource.namespace or namespace,
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


async def rancher_norman_resource_action_invoke_tool(
    schema_id: str,
    resource_id: str,
    action_name: str,
    payload_json: str | None = None,
    instance: str | None = None,
) -> GenericResourceActionResult:
    """Public MCP wrapper for Norman generic action invocation."""

    return await rancher_norman_resource_action_invoke(
        schema_id=schema_id,
        resource_id=resource_id,
        action_name=action_name,
        payload_json=payload_json,
        instance=instance,
    )


async def rancher_norman_resource_link_follow_tool(
    schema_id: str,
    resource_id: str,
    link_name: str,
    instance: str | None = None,
) -> GenericResourceLinkResult:
    """Public MCP wrapper for Norman generic link follow."""

    return await rancher_norman_resource_link_follow(
        schema_id=schema_id,
        resource_id=resource_id,
        link_name=link_name,
        instance=instance,
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
