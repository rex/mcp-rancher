"""Steve generic resource list/get implementations."""

from __future__ import annotations

from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceDetail, GenericResourceList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import build_steve_list_query_params
from rancher_mcp.services.resources import (
    build_collection_path,
    build_resource_detail_model,
    build_resource_list_model,
    build_resource_path,
    schema_reference_from_payload,
)


async def _fetch_steve_resource_list(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    schema_id: str,
    limit: int | None,
    continue_token: str | None,
    label_selector: str | None,
    field_selector: str | None,
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
    query_params = build_steve_list_query_params(
        limit=limit,
        continue_token=continue_token,
        label_selector=label_selector,
        field_selector=field_selector,
        params_json=params_json,
    )
    collection_path = build_collection_path(schema, namespace=namespace)
    payload = await client.get_json(collection_path, params=query_params or None)
    return build_resource_list_model(
        instance=instance_name,
        plane="steve",
        schema=schema,
        payload=payload,
        cluster_id=cluster_id,
        namespace=namespace,
        applied_query_params=query_params,
    )


async def rancher_steve_resource_list(
    schema_id: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    limit: int | None = None,
    continue_token: str | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
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
            limit,
            continue_token,
            label_selector,
            field_selector,
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
            limit,
            continue_token,
            label_selector,
            field_selector,
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


async def rancher_steve_resource_list_tool(
    schema_id: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    limit: int | None = None,
    continue_token: str | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    params_json: str | None = None,
    instance: str | None = None,
) -> GenericResourceList:
    """List any Steve Kubernetes-proxy resource collection by raw schema id, cluster,
    and optional namespace with label or field selectors — the escape hatch for
    kinds with no curated `rancher_*_list` tool yet."""

    return await rancher_steve_resource_list(
        schema_id=schema_id,
        cluster_id=cluster_id,
        namespace=namespace,
        limit=limit,
        continue_token=continue_token,
        label_selector=label_selector,
        field_selector=field_selector,
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
    """Fetch one Steve Kubernetes-proxy resource's full untyped payload by schema id,
    cluster, and resource id — the escape hatch for kinds with no curated
    `rancher_*_get` tool yet."""

    return await rancher_steve_resource_get(
        schema_id=schema_id,
        resource_id=resource_id,
        cluster_id=cluster_id,
        namespace=namespace,
        instance=instance,
    )
