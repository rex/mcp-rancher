"""Curated Rancher catalog tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.apps_catalogs import RancherCatalogDetail, RancherCatalogList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.apps_catalogs.shared import (
    build_catalog_query_params,
    catalog_summary_from_payload,
    data_items,
)
from rancher_mcp.tools.support.values import mapping_value


async def _fetch_catalogs_list(
    instance_name: str,
    limit: int | None,
    state: str | None,
    kind: str | None,
    helm_version: str | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherCatalogList:
    """Fetch and normalize the Rancher catalogs collection."""

    query_params = build_catalog_query_params(
        limit=limit,
        state=state,
        kind=kind,
        helm_version=helm_version,
        sort_by=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/catalogs", params=query_params or None)
    catalogs = [catalog_summary_from_payload(item) for item in data_items(payload)]
    return RancherCatalogList(
        instance=instance_name,
        catalog_count=len(catalogs),
        applied_query_params=query_params,
        catalogs=catalogs,
    )


async def rancher_catalogs_list(
    limit: int | None = None,
    state: str | None = None,
    kind: str | None = None,
    helm_version: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherCatalogList:
    """List Rancher catalogs with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_catalogs_list(
            instance_name,
            limit,
            state,
            kind,
            helm_version,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_catalogs_list(
            instance_name,
            limit,
            state,
            kind,
            helm_version,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_catalog_get(
    catalog_id: str,
    client: ManagementDiscoveryClient,
) -> RancherCatalogDetail:
    """Fetch and normalize one Rancher catalog."""

    payload = await client.get_json(f"/v3/catalogs/{catalog_id}")
    summary = catalog_summary_from_payload(payload)
    return RancherCatalogDetail.model_validate(payload).model_copy(
        update={
            "condition_types_true": summary.condition_types_true,
            "action_keys": sorted(mapping_value(payload, "actions") or {}),
            "link_keys": sorted(mapping_value(payload, "links") or {}),
            "payload": dict(payload),
        }
    )


async def rancher_catalog_get(
    catalog_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherCatalogDetail:
    """Fetch one Rancher catalog by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_catalog_get(catalog_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_catalog_get(catalog_id, managed_client)


async def rancher_catalogs_list_tool(
    limit: int | None = None,
    state: str | None = None,
    kind: str | None = None,
    helm_version: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherCatalogList:
    """Public MCP wrapper for curated catalogs list."""

    return await rancher_catalogs_list(
        limit=limit,
        state=state,
        kind=kind,
        helm_version=helm_version,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_catalog_get_tool(
    catalog_id: str,
    instance: str | None = None,
) -> RancherCatalogDetail:
    """Public MCP wrapper for curated catalog detail."""

    return await rancher_catalog_get(catalog_id=catalog_id, instance=instance)
