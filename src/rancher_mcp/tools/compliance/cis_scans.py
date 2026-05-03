"""Curated Rancher CIS scan run tools."""

from __future__ import annotations

from typing import cast

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.compliance import (
    RancherCisScanDetail,
    RancherCisScanList,
    RancherCisScanSummary,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.support.values import mapping_value


def _data_items(payload: dict[str, object]) -> list[dict[str, object]]:
    raw = payload.get("data")
    if not isinstance(raw, list):
        return []
    return [item for item in cast(list[object], raw) if isinstance(item, dict)]


def _scan_summary(item: dict[str, object]) -> RancherCisScanSummary:
    return RancherCisScanSummary.model_validate(item)


async def _fetch_cis_scans_list(
    instance_name: str,
    limit: int | None,
    cluster_id: str | None,
    state: str | None,
    client: ManagementDiscoveryClient,
) -> RancherCisScanList:
    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if state is not None:
        params["state"] = state
    payload = await client.get_json("/v3/cisscans", params=params or None)
    scans = [_scan_summary(item) for item in _data_items(payload)]
    return RancherCisScanList(
        instance=instance_name,
        scan_count=len(scans),
        applied_query_params=params,
        scans=scans,
    )


async def rancher_cis_scans_list(
    limit: int | None = None,
    cluster_id: str | None = None,
    state: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherCisScanList:
    """List CIS scan runs on the Rancher management server."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cis_scans_list(instance_name, limit, cluster_id, state, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cis_scans_list(instance_name, limit, cluster_id, state, managed_client)


async def _fetch_cis_scan_get(
    scan_id: str,
    client: ManagementDiscoveryClient,
) -> RancherCisScanDetail:
    payload = await client.get_json(f"/v3/cisscans/{scan_id}")
    status = mapping_value(payload, "status") or {}
    base = RancherCisScanDetail.model_validate(payload)
    return base.model_copy(update={"status": dict(status), "payload": dict(payload)})


async def rancher_cis_scan_get(
    scan_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherCisScanDetail:
    """Fetch one CIS scan run by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cis_scan_get(scan_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cis_scan_get(scan_id, managed_client)


async def rancher_cis_scans_list_tool(
    limit: int | None = None,
    cluster_id: str | None = None,
    state: str | None = None,
    instance: str | None = None,
) -> RancherCisScanList:
    """List CIS scan runs (requires CIS Benchmark app to be installed)."""

    return await rancher_cis_scans_list(
        limit=limit, cluster_id=cluster_id, state=state, instance=instance
    )


async def rancher_cis_scan_get_tool(
    scan_id: str,
    instance: str | None = None,
) -> RancherCisScanDetail:
    """Fetch one CIS scan run by id."""

    return await rancher_cis_scan_get(scan_id=scan_id, instance=instance)
