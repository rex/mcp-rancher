"""Norman generic resource list/get implementations."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceDetail, GenericResourceList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import build_norman_list_query_params
from rancher_mcp.services.resources import (
    build_resource_detail_model,
    build_resource_list_model,
    build_resource_path,
    schema_reference_from_payload,
)


async def _fetch_norman_resource_list(
    instance_name: str,
    schema_id: str,
    limit: int | None,
    marker: str | None,
    sort_by: str | None,
    reverse: bool | None,
    filters_json: str | None,
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
    query_params = build_norman_list_query_params(
        limit=limit,
        marker=marker,
        sort_by=sort_by,
        reverse=reverse,
        filters_json=filters_json,
        params_json=params_json,
    )
    payload = await client.get_json(schema.collection_path, params=query_params or None)
    return build_resource_list_model(
        instance=instance_name,
        plane="norman",
        schema=schema,
        payload=payload,
        applied_query_params=query_params,
    )


async def rancher_norman_resource_list(
    schema_id: str,
    limit: int | None = None,
    marker: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    filters_json: str | None = None,
    params_json: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> GenericResourceList:
    """List Norman resources for a schema type."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_norman_resource_list(
            instance_name,
            schema_id,
            limit,
            marker,
            sort_by,
            reverse,
            filters_json,
            params_json,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_norman_resource_list(
            instance_name,
            schema_id,
            limit,
            marker,
            sort_by,
            reverse,
            filters_json,
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


async def rancher_norman_resource_list_tool(
    schema_id: str,
    limit: int | None = None,
    marker: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    filters_json: str | None = None,
    params_json: str | None = None,
    instance: str | None = None,
) -> GenericResourceList:
    """Public MCP wrapper for Norman generic list."""

    return await rancher_norman_resource_list(
        schema_id=schema_id,
        limit=limit,
        marker=marker,
        sort_by=sort_by,
        reverse=reverse,
        filters_json=filters_json,
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
