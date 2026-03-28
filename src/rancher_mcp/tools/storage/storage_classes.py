# pyright: reportPrivateUsage=false
"""Curated Rancher storage-class tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.storage import RancherStorageClassDetail, RancherStorageClassList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.storage.paths import (
    _storage_class_collection_path,
    _storage_class_resource_path,
)
from rancher_mcp.tools.storage.shared import (
    _build_list_query_params,
    _items,
    _mapping_value,
    _storage_class_summary_from_payload,
    _string_dict,
    _string_list,
)


async def _fetch_storage_classes_list(
    instance_name: str,
    cluster_id: str,
    default_only: bool | None,
    limit: int | None,
    client: ManagementDiscoveryClient,
) -> RancherStorageClassList:
    """Fetch and normalize storage classes through Rancher's raw Kubernetes proxy."""

    query_params = _build_list_query_params(limit=limit)
    payload = await client.get_json(
        _storage_class_collection_path(cluster_id),
        params=query_params or None,
    )
    storage_classes = [_storage_class_summary_from_payload(item) for item in _items(payload)]
    if default_only is True:
        storage_classes = [item for item in storage_classes if item.default_class is True]
    return RancherStorageClassList(
        instance=instance_name,
        cluster_id=cluster_id,
        storage_class_count=len(storage_classes),
        applied_query_params=query_params,
        storage_classes=storage_classes,
    )


async def rancher_storage_classes_list(
    cluster_id: str = "local",
    default_only: bool | None = None,
    limit: int | None = None,
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
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_storage_classes_list(
            instance_name,
            cluster_id,
            default_only,
            limit,
            managed_client,
        )


async def _fetch_storage_class_get(
    instance_name: str,
    cluster_id: str,
    storage_class_name: str,
    client: ManagementDiscoveryClient,
) -> RancherStorageClassDetail:
    """Fetch and normalize one storage class."""

    payload = await client.get_json(_storage_class_resource_path(cluster_id, storage_class_name))
    summary = _storage_class_summary_from_payload(payload)
    metadata = _mapping_value(payload, "metadata") or {}
    return RancherStorageClassDetail(
        name=summary.name,
        provisioner=summary.provisioner,
        reclaim_policy=summary.reclaim_policy,
        volume_binding_mode=summary.volume_binding_mode,
        allow_volume_expansion=summary.allow_volume_expansion,
        default_class=summary.default_class,
        parameter_keys=summary.parameter_keys,
        mount_options=_string_list(payload.get("mountOptions")),
        annotation_keys=sorted(_string_dict(_mapping_value(metadata, "annotations") or {})),
        payload=dict(payload),
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
    instance: str | None = None,
) -> RancherStorageClassList:
    """Public MCP wrapper for curated storage-class list."""

    return await rancher_storage_classes_list(
        cluster_id=cluster_id,
        default_only=default_only,
        limit=limit,
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
