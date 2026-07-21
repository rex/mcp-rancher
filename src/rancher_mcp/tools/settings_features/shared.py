"""Shared helpers for curated settings and features tools."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.settings_features import (
    RancherFeatureSummary,
    RancherSettingSummary,
)
from rancher_mcp.tools.support.collections import object_items


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


_MAX_VALUE_LEN = 200


def _shape_setting_value(value: str | None) -> dict[str, object]:
    """Shape a raw setting value (L-3a): a JSON object collapses to its ``keys``
    (the shape is the signal, not the 4 KB of args), a PEM to a marker, and any
    long value is truncated. Returns model-copy fields; empty when no shaping."""

    if not value:
        return {}
    if "BEGIN CERTIFICATE" in value:
        return {"value": None, "value_type": "certificate", "truncated": True, "length": len(value)}
    stripped = value.strip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            keys = cast("dict[str, object]", parsed).keys()
            return {
                "value": None,
                "value_type": "json",
                "truncated": True,
                "length": len(value),
                "keys": sorted(str(key) for key in keys),
            }
    if len(value) > _MAX_VALUE_LEN:
        return {"value": value[:_MAX_VALUE_LEN], "truncated": True, "length": len(value)}
    return {}


def _setting_summary_from_payload(payload: Mapping[str, object]) -> RancherSettingSummary:
    """Normalize one Rancher setting payload, shaping oversized values (L-3a)."""

    summary = RancherSettingSummary.model_validate(payload)
    shaped = _shape_setting_value(summary.value)
    return summary.model_copy(update=shaped) if shaped else summary


def _feature_summary_from_payload(payload: Mapping[str, object]) -> RancherFeatureSummary:
    """Normalize one Rancher feature payload."""

    return RancherFeatureSummary.model_validate(payload)


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher list payload."""

    return object_items(payload, field="data")


build_feature_query_params = _build_feature_query_params
build_settings_query_params = _build_settings_query_params
data_items = _data_items
feature_summary_from_payload = _feature_summary_from_payload
setting_summary_from_payload = _setting_summary_from_payload
