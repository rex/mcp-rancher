"""Curated Rancher etcd-backup tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.logging_backups import RancherEtcdBackupDetail, RancherEtcdBackupList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.logging_backups.shared import (
    action_keys,
    build_query_params,
    data_items,
    etcd_backup_summary_from_payload,
    link_keys,
)
from rancher_mcp.tools.support.values import mapping_value


async def _fetch_etcd_backups_list(
    instance_name: str,
    limit: int | None,
    cluster_id: str | None,
    filename: str | None,
    manual: bool | None,
    name: str | None,
    state: str | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherEtcdBackupList:
    """Fetch and normalize the Rancher etcd-backup collection."""

    query_params = build_query_params(
        limit=limit,
        clusterId=cluster_id,
        filename=filename,
        manual=manual,
        name=name,
        state=state,
        sort=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/etcdbackups", params=query_params or None)
    etcd_backups = [etcd_backup_summary_from_payload(item) for item in data_items(payload)]
    return RancherEtcdBackupList(
        instance=instance_name,
        etcd_backup_count=len(etcd_backups),
        applied_query_params=query_params,
        etcd_backups=etcd_backups,
    )


async def rancher_etcd_backups_list(
    limit: int | None = None,
    cluster_id: str | None = None,
    filename: str | None = None,
    manual: bool | None = None,
    name: str | None = None,
    state: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherEtcdBackupList:
    """List Rancher etcd backups with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_etcd_backups_list(
            instance_name,
            limit,
            cluster_id,
            filename,
            manual,
            name,
            state,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_etcd_backups_list(
            instance_name,
            limit,
            cluster_id,
            filename,
            manual,
            name,
            state,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_etcd_backup_get(
    etcd_backup_id: str,
    client: ManagementDiscoveryClient,
) -> RancherEtcdBackupDetail:
    """Fetch and normalize one Rancher etcd backup."""

    payload = await client.get_json(f"/v3/etcdbackups/{etcd_backup_id}")
    return RancherEtcdBackupDetail.model_validate(payload).model_copy(
        update={
            "backup_config": mapping_value(payload, "backupConfig") or {},
            "status": mapping_value(payload, "status") or {},
            "status_keys": sorted((mapping_value(payload, "status") or {}).keys()),
            "action_keys": action_keys(payload),
            "link_keys": link_keys(payload),
            "payload": dict(payload),
        }
    )


async def rancher_etcd_backup_get(
    etcd_backup_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherEtcdBackupDetail:
    """Fetch one Rancher etcd backup by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_etcd_backup_get(etcd_backup_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_etcd_backup_get(etcd_backup_id, managed_client)


async def rancher_etcd_backups_list_tool(
    limit: int | None = None,
    cluster_id: str | None = None,
    filename: str | None = None,
    manual: bool | None = None,
    name: str | None = None,
    state: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherEtcdBackupList:
    """Public MCP wrapper for curated etcd-backup list."""

    return await rancher_etcd_backups_list(
        limit=limit,
        cluster_id=cluster_id,
        filename=filename,
        manual=manual,
        name=name,
        state=state,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_etcd_backup_get_tool(
    etcd_backup_id: str,
    instance: str | None = None,
) -> RancherEtcdBackupDetail:
    """Public MCP wrapper for curated etcd-backup detail."""

    return await rancher_etcd_backup_get(etcd_backup_id=etcd_backup_id, instance=instance)
