# pyright: reportUnusedFunction=false
"""Shared helpers for curated settings and features tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.settings_features import (
    RancherFeatureSummary,
    RancherSettingSummary,
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
