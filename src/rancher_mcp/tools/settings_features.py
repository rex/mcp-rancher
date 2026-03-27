"""Curated Rancher settings and features read-only tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from mcp.server.fastmcp import FastMCP

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.settings_features import (
    RancherFeatureDetail,
    RancherFeatureList,
    RancherFeatureSummary,
    RancherSettingDetail,
    RancherSettingList,
    RancherSettingSummary,
)
from rancher_mcp.services.instances import resolve_instance


async def _fetch_settings_list(
    instance_name: str,
    limit: int | None,
    source: str | None,
    customized: bool | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherSettingList:
    """Fetch and normalize the Rancher settings collection."""

    query_params = _build_settings_query_params(
        limit=limit,
        source=source,
        customized=customized,
        sort_by=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/settings", params=query_params or None)
    settings = [_setting_summary_from_payload(item) for item in _data_items(payload)]
    return RancherSettingList(
        instance=instance_name,
        setting_count=len(settings),
        applied_query_params=query_params,
        settings=settings,
    )


async def rancher_settings_list(
    limit: int | None = None,
    source: str | None = None,
    customized: bool | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherSettingList:
    """List Rancher settings with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_settings_list(
            instance_name,
            limit,
            source,
            customized,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_settings_list(
            instance_name,
            limit,
            source,
            customized,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_setting_get(
    instance_name: str,
    setting_id: str,
    client: ManagementDiscoveryClient,
) -> RancherSettingDetail:
    """Fetch and normalize one Rancher setting."""

    payload = await client.get_json(f"/v3/settings/{setting_id}")
    summary = _setting_summary_from_payload(payload)
    return RancherSettingDetail(
        id=summary.id,
        name=summary.name,
        value=summary.value,
        default=summary.default,
        source=summary.source,
        customized=summary.customized,
        payload=dict(payload),
    )


async def rancher_setting_get(
    setting_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherSettingDetail:
    """Fetch one Rancher setting by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_setting_get(instance_name, setting_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_setting_get(instance_name, setting_id, managed_client)


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


def register_settings_feature_tools(mcp: FastMCP) -> None:
    """Register curated settings/features tools with the FastMCP server."""

    mcp.tool(name="rancher_settings_list")(rancher_settings_list_tool)
    mcp.tool(name="rancher_setting_get")(rancher_setting_get_tool)
    mcp.tool(name="rancher_features_list")(rancher_features_list_tool)
    mcp.tool(name="rancher_feature_get")(rancher_feature_get_tool)


async def rancher_settings_list_tool(
    limit: int | None = None,
    source: str | None = None,
    customized: bool | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherSettingList:
    """Public MCP wrapper for curated settings list."""

    return await rancher_settings_list(
        limit=limit,
        source=source,
        customized=customized,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_setting_get_tool(
    setting_id: str,
    instance: str | None = None,
) -> RancherSettingDetail:
    """Public MCP wrapper for curated setting detail."""

    return await rancher_setting_get(
        setting_id=setting_id,
        instance=instance,
    )


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


def _build_settings_query_params(
    *,
    limit: int | None,
    source: str | None,
    customized: bool | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher settings collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if source is not None:
        params["source"] = source
    if customized is not None:
        params["customized"] = customized
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_feature_query_params(
    *,
    limit: int | None,
    state: str | None,
    enabled: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher features collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if state is not None:
        params["state"] = state
    if enabled is not None:
        params["value"] = enabled
    return params


def _setting_summary_from_payload(payload: Mapping[str, object]) -> RancherSettingSummary:
    """Normalize one Rancher setting payload."""

    setting_id = _string_value(payload, "id")
    name = _string_value(payload, "name")
    return RancherSettingSummary(
        id=setting_id or name or "<unknown-setting>",
        name=name or setting_id or "<unknown-setting>",
        value=_string_value(payload, "value"),
        default=_string_value(payload, "default"),
        source=_string_value(payload, "source"),
        customized=_bool_value(payload, "customized"),
    )


def _feature_summary_from_payload(payload: Mapping[str, object]) -> RancherFeatureSummary:
    """Normalize one Rancher feature payload."""

    feature_id = _string_value(payload, "id")
    name = _string_value(payload, "name")
    status = _mapping_value(payload, "status")
    return RancherFeatureSummary(
        id=feature_id or name or "<unknown-feature>",
        name=name or feature_id or "<unknown-feature>",
        enabled=_bool_value(payload, "value"),
        state=_string_value(payload, "state"),
        description=_string_value(status, "description"),
        dynamic=_bool_value(status, "dynamic"),
        default=_bool_value(status, "default"),
        transitioning=_string_value(payload, "transitioning"),
        transitioning_message=_string_value(payload, "transitioningMessage"),
    )


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher list payload."""

    raw_items = payload.get("data")
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, object]] = []
    typed_items = cast(list[object], raw_items)
    for item in typed_items:
        if isinstance(item, dict):
            items.append(cast(dict[str, object], item))
    return items


def _mapping_value(
    payload: Mapping[str, object] | None,
    key: str,
) -> dict[str, object] | None:
    """Read one nested mapping value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    if not isinstance(raw_value, dict):
        return None
    return cast(dict[str, object], raw_value)


def _string_value(payload: Mapping[str, object] | None, key: str) -> str | None:
    """Read one string value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, str) else None


def _bool_value(payload: Mapping[str, object] | None, key: str) -> bool | None:
    """Read one boolean value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, bool) else None
