"""Generic schema-driven resource list/get tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceDetail, GenericResourceList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resources import (
    build_collection_path,
    build_resource_detail_model,
    build_resource_list_model,
    build_resource_path,
    parse_query_params,
    schema_reference_from_payload,
)


async def _fetch_norman_resource_list(
    instance_name: str,
    schema_id: str,
    params_json: str | None,
    client: ManagementDiscoveryClient,
) -> GenericResourceList:
    """Fetch a Norman collection by schema id."""

    schema_payload = await client.get_json(f"/v3/schemas/{schema_id}")
    schema = schema_reference_from_payload(
        plane="norman",
        cluster_id=None,
        schema_id=schema_id,
        payload=schema_payload,
    )
    params = parse_query_params(params_json)
    payload = await client.get_json(schema.collection_path, params=params or None)
    return build_resource_list_model(
        instance=instance_name,
        plane="norman",
        schema=schema,
        payload=payload,
    )


async def rancher_norman_resource_list(
    schema_id: str,
    params_json: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> GenericResourceList:
    """List Norman resources for a schema type."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_norman_resource_list(instance_name, schema_id, params_json, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_norman_resource_list(
            instance_name,
            schema_id,
            params_json,
            managed_client,
        )


async def _fetch_norman_resource_get(
    instance_name: str,
    schema_id: str,
    resource_id: str,
    client: ManagementDiscoveryClient,
) -> GenericResourceDetail:
    """Fetch one Norman resource by schema id and resource id."""

    schema_payload = await client.get_json(f"/v3/schemas/{schema_id}")
    schema = schema_reference_from_payload(
        plane="norman",
        cluster_id=None,
        schema_id=schema_id,
        payload=schema_payload,
    )
    resource_path = build_resource_path(schema, resource_id=resource_id)
    payload = await client.get_json(resource_path)
    return build_resource_detail_model(
        instance=instance_name,
        plane="norman",
        schema=schema,
        requested_resource_id=resource_id,
        requested_path=resource_path,
        payload=payload,
    )


async def rancher_norman_resource_get(
    schema_id: str,
    resource_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> GenericResourceDetail:
    """Fetch one Norman resource by schema type and id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_norman_resource_get(instance_name, schema_id, resource_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_norman_resource_get(
            instance_name,
            schema_id,
            resource_id,
            managed_client,
        )


async def _fetch_steve_resource_list(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    schema_id: str,
    params_json: str | None,
    client: SteveDiscoveryClient,
) -> GenericResourceList:
    """Fetch a Steve collection by schema id."""

    schema_payload = await client.get_json(f"/schemas/{schema_id}")
    schema = schema_reference_from_payload(
        plane="steve",
        cluster_id=cluster_id,
        schema_id=schema_id,
        payload=schema_payload,
    )
    params = parse_query_params(params_json)
    collection_path = build_collection_path(schema, namespace=namespace)
    payload = await client.get_json(collection_path, params=params or None)
    return build_resource_list_model(
        instance=instance_name,
        plane="steve",
        schema=schema,
        payload=payload,
        cluster_id=cluster_id,
        namespace=namespace,
    )


async def rancher_steve_resource_list(
    schema_id: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    params_json: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> GenericResourceList:
    """List Steve resources for a schema type."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_steve_resource_list(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            params_json,
            client,
        )
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as proxy_client:
        return await _fetch_steve_resource_list(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            params_json,
            proxy_client,
        )


async def _fetch_steve_resource_get(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    schema_id: str,
    resource_id: str,
    client: SteveDiscoveryClient,
) -> GenericResourceDetail:
    """Fetch one Steve resource by schema id and resource id."""

    schema_payload = await client.get_json(f"/schemas/{schema_id}")
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
    payload = await client.get_json(resource_path)
    return build_resource_detail_model(
        instance=instance_name,
        plane="steve",
        schema=schema,
        requested_resource_id=resource_id,
        requested_path=resource_path,
        payload=payload,
        cluster_id=cluster_id,
        namespace=namespace,
    )


async def rancher_steve_resource_get(
    schema_id: str,
    resource_id: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> GenericResourceDetail:
    """Fetch one Steve resource by schema type and id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_steve_resource_get(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            resource_id,
            client,
        )
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as proxy_client:
        return await _fetch_steve_resource_get(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            resource_id,
            proxy_client,
        )


async def rancher_norman_resource_list_tool(
    schema_id: str,
    params_json: str | None = None,
    instance: str | None = None,
) -> GenericResourceList:
    """Public MCP wrapper for Norman generic list."""

    return await rancher_norman_resource_list(
        schema_id=schema_id,
        params_json=params_json,
        instance=instance,
    )


async def rancher_norman_resource_get_tool(
    schema_id: str,
    resource_id: str,
    instance: str | None = None,
) -> GenericResourceDetail:
    """Public MCP wrapper for Norman generic get."""

    return await rancher_norman_resource_get(
        schema_id=schema_id,
        resource_id=resource_id,
        instance=instance,
    )


async def rancher_steve_resource_list_tool(
    schema_id: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    params_json: str | None = None,
    instance: str | None = None,
) -> GenericResourceList:
    """Public MCP wrapper for Steve generic list."""

    return await rancher_steve_resource_list(
        schema_id=schema_id,
        cluster_id=cluster_id,
        namespace=namespace,
        params_json=params_json,
        instance=instance,
    )


async def rancher_steve_resource_get_tool(
    schema_id: str,
    resource_id: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    instance: str | None = None,
) -> GenericResourceDetail:
    """Public MCP wrapper for Steve generic get."""

    return await rancher_steve_resource_get(
        schema_id=schema_id,
        resource_id=resource_id,
        cluster_id=cluster_id,
        namespace=namespace,
        instance=instance,
    )
