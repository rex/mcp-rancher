"""Curated Rancher CIS scan profile tools."""

from __future__ import annotations

from typing import cast

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.compliance import (
    RancherCisScanProfileDetail,
    RancherCisScanProfileList,
    RancherCisScanProfileSummary,
)
from rancher_mcp.services.instances import resolve_instance


def _data_items(payload: dict[str, object]) -> list[dict[str, object]]:
    raw = payload.get("data")
    if not isinstance(raw, list):
        return []
    return [item for item in cast(list[object], raw) if isinstance(item, dict)]


def _profile_summary(item: dict[str, object]) -> RancherCisScanProfileSummary:
    return RancherCisScanProfileSummary.model_validate(item)


async def _fetch_cis_scan_profiles_list(
    instance_name: str,
    limit: int | None,
    cluster_id: str | None,
    client: ManagementDiscoveryClient,
) -> RancherCisScanProfileList:
    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    payload = await client.get_json("/v3/cisscanprofiles", params=params or None)
    profiles = [_profile_summary(item) for item in _data_items(payload)]
    return RancherCisScanProfileList(
        instance=instance_name,
        profile_count=len(profiles),
        applied_query_params=params,
        profiles=profiles,
    )


async def rancher_cis_scan_profiles_list(
    limit: int | None = None,
    cluster_id: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherCisScanProfileList:
    """List CIS scan profiles available on the Rancher management server."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cis_scan_profiles_list(instance_name, limit, cluster_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cis_scan_profiles_list(instance_name, limit, cluster_id, managed_client)


async def _fetch_cis_scan_profile_get(
    profile_id: str,
    client: ManagementDiscoveryClient,
) -> RancherCisScanProfileDetail:
    payload = await client.get_json(f"/v3/cisscanprofiles/{profile_id}")
    tests_raw = payload.get("tests")
    tests: list[dict[str, object]] = (
        [t for t in cast(list[object], tests_raw) if isinstance(t, dict)]
        if isinstance(tests_raw, list)
        else []
    )
    base = RancherCisScanProfileDetail.model_validate(payload)
    return base.model_copy(update={"tests": tests, "payload": dict(payload)})


async def rancher_cis_scan_profile_get(
    profile_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherCisScanProfileDetail:
    """Fetch one CIS scan profile by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cis_scan_profile_get(profile_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cis_scan_profile_get(profile_id, managed_client)


async def rancher_cis_scan_profiles_list_tool(
    limit: int | None = None,
    cluster_id: str | None = None,
    instance: str | None = None,
) -> RancherCisScanProfileList:
    """List CIS scan profiles (requires CIS Benchmark app to be installed)."""

    return await rancher_cis_scan_profiles_list(
        limit=limit, cluster_id=cluster_id, instance=instance
    )


async def rancher_cis_scan_profile_get_tool(
    profile_id: str,
    instance: str | None = None,
) -> RancherCisScanProfileDetail:
    """Fetch one CIS scan profile by id."""

    return await rancher_cis_scan_profile_get(profile_id=profile_id, instance=instance)
