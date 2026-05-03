"""Curated Rancher storage-class tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.storage import RancherStorageClassDetail, RancherStorageClassList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resources.builders_pagination import next_page_token_from_payload
from rancher_mcp.tools.storage.paths import (
    storage_class_collection_path,
    storage_class_resource_path,
)
from rancher_mcp.tools.storage.shared import (
    build_list_query_params,
    items,
    storage_class_summary_from_payload,
    string_list,
)
from rancher_mcp.tools.support.values import mapping_value, string_dict


async def _fetch_storage_classes_list(
    instance_name: str,
    cluster_id: str,
    default_only: bool | None,
    limit: int | None,
    client: ManagementDiscoveryClient,
    page_token: str | None = None,
) -> RancherStorageClassList:
    """Fetch and normalize storage classes through Rancher's raw Kubernetes proxy."""

    query_params = build_list_query_params(limit=limit, continue_token=page_token)
    payload = await client.get_json(
        storage_class_collection_path(cluster_id),
        params=query_params or None,
    )
    storage_classes = [storage_class_summary_from_payload(item) for item in items(payload)]
    if default_only is True:
        storage_classes = [item for item in storage_classes if item.default_class is True]
    return RancherStorageClassList(
        instance=instance_name,
        cluster_id=cluster_id,
        storage_class_count=len(storage_classes),
        next_page_token=next_page_token_from_payload(payload),
        applied_query_params=query_params,
        storage_classes=storage_classes,
        suggested_next_steps=[
            "rancher_storage_class_get",
            "rancher_persistent_volumes_list",
            "rancher_persistent_volume_claims_list",
        ],
    )


async def rancher_storage_classes_list(
    cluster_id: str = "local",
    default_only: bool | None = None,
    limit: int | None = None,
    page_token: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherStorageClassList:
    """List storage classes with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_storage_classes_list(
            instance_name,
            cluster_id,
            default_only,
            limit,
            client,
            page_token,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_storage_classes_list(
            instance_name,
            cluster_id,
            default_only,
            limit,
            managed_client,
            page_token,
        )


async def _fetch_storage_class_get(
    instance_name: str,
    cluster_id: str,
    storage_class_name: str,
    client: ManagementDiscoveryClient,
) -> RancherStorageClassDetail:
    """Fetch and normalize one storage class."""

    payload = await client.get_json(storage_class_resource_path(cluster_id, storage_class_name))
    summary = storage_class_summary_from_payload(payload)
    metadata = mapping_value(payload, "metadata") or {}
    return RancherStorageClassDetail.model_validate(payload).model_copy(
        update={
            "default_class": summary.default_class,
            "parameter_keys": summary.parameter_keys,
            "mount_options": string_list(payload.get("mountOptions")),
            "annotation_keys": sorted(string_dict(mapping_value(metadata, "annotations") or {})),
            "payload": dict(payload),
            "suggested_next_steps": [
                "rancher_storage_classes_list",
                "rancher_persistent_volumes_list",
            ],
        }
    )


async def rancher_storage_class_get(
    storage_class_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherStorageClassDetail:
    """Fetch one storage class by name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_storage_class_get(
            instance_name,
            cluster_id,
            storage_class_name,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_storage_class_get(
            instance_name,
            cluster_id,
            storage_class_name,
            managed_client,
        )


async def rancher_storage_classes_list_tool(
    cluster_id: str = "local",
    default_only: bool | None = None,
    limit: int | None = None,
    page_token: str | None = None,
    instance: str | None = None,
) -> RancherStorageClassList:
    """Public MCP wrapper for curated storage-class list."""

    return await rancher_storage_classes_list(
        cluster_id=cluster_id,
        default_only=default_only,
        limit=limit,
        page_token=page_token,
        instance=instance,
    )


async def rancher_storage_class_get_tool(
    storage_class_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherStorageClassDetail:
    """Public MCP wrapper for curated storage-class detail."""

    return await rancher_storage_class_get(
        storage_class_name=storage_class_name,
        cluster_id=cluster_id,
        instance=instance,
    )
