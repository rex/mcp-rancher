# pyright: reportPrivateUsage=false
"""Curated Rancher feature tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.settings_features import RancherFeatureDetail, RancherFeatureList
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.settings_features.shared import (
    _build_feature_query_params,
    _data_items,
    _feature_summary_from_payload,
)


async def _fetch_features_list(
    instance_name: str,
    limit: int | None,
    state: str | None,
    enabled: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherFeatureList:
    """Fetch and normalize the Rancher features collection."""

    query_params = _build_feature_query_params(
        limit=limit,
        state=state,
        enabled=enabled,
    )
    payload = await client.get_json("/v3/features", params=query_params or None)
    features = [_feature_summary_from_payload(item) for item in _data_items(payload)]
    return RancherFeatureList(
        instance=instance_name,
        feature_count=len(features),
        applied_query_params=query_params,
        features=features,
    )


async def rancher_features_list(
    limit: int | None = None,
    state: str | None = None,
    enabled: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherFeatureList:
    """List Rancher features with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_features_list(
            instance_name,
            limit,
            state,
            enabled,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_features_list(
            instance_name,
            limit,
            state,
            enabled,
            managed_client,
        )


async def _fetch_feature_get(
    instance_name: str,
    feature_id: str,
    client: ManagementDiscoveryClient,
) -> RancherFeatureDetail:
    """Fetch and normalize one Rancher feature flag."""

    payload = await client.get_json(f"/v3/features/{feature_id}")
    summary = _feature_summary_from_payload(payload)
    return RancherFeatureDetail(
        id=summary.id,
        name=summary.name,
        enabled=summary.enabled,
        state=summary.state,
        description=summary.description,
        dynamic=summary.dynamic,
        default=summary.default,
        transitioning=summary.transitioning,
        transitioning_message=summary.transitioning_message,
        payload=dict(payload),
    )


async def rancher_feature_get(
    feature_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherFeatureDetail:
    """Fetch one Rancher feature by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_feature_get(instance_name, feature_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_feature_get(instance_name, feature_id, managed_client)


async def rancher_features_list_tool(
    limit: int | None = None,
    state: str | None = None,
    enabled: bool | None = None,
    instance: str | None = None,
) -> RancherFeatureList:
    """Public MCP wrapper for curated features list."""

    return await rancher_features_list(
        limit=limit,
        state=state,
        enabled=enabled,
        instance=instance,
    )


async def rancher_feature_get_tool(
    feature_id: str,
    instance: str | None = None,
) -> RancherFeatureDetail:
    """Public MCP wrapper for curated feature detail."""

    return await rancher_feature_get(
        feature_id=feature_id,
        instance=instance,
    )
