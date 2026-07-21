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


def _shape_setting_value(value: str | None, *, field: str = "value") -> dict[str, object]:
    """Shape a raw setting field (L-3a for ``value``; M-SETTINGS reuses this
    unchanged for ``default``): a JSON object collapses to its ``keys`` (the
    shape is the signal, not the KBs of blob), a PEM to a marker, and any long
    value is truncated. ``field`` namespaces the emitted keys (``value`` /
    ``valueType`` / ... vs ``default`` / ``defaultType`` / ...) so shaping both
    ``value`` and ``default`` on one setting can never clobber each other.
    Returns model-copy fields; empty when no shaping applies."""

    if not value:
        return {}
    type_key = "value_type" if field == "value" else f"{field}_type"
    truncated_key = "truncated" if field == "value" else f"{field}_truncated"
    length_key = "length" if field == "value" else f"{field}_length"
    keys_key = "keys" if field == "value" else f"{field}_keys"

    if "BEGIN CERTIFICATE" in value:
        return {field: None, type_key: "certificate", truncated_key: True, length_key: len(value)}
    stripped = value.strip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            keys = cast("dict[str, object]", parsed).keys()
            return {
                field: None,
                type_key: "json",
                truncated_key: True,
                length_key: len(value),
                keys_key: sorted(str(key) for key in keys),
            }
    if len(value) > _MAX_VALUE_LEN:
        return {field: value[:_MAX_VALUE_LEN], truncated_key: True, length_key: len(value)}
    return {}


def _setting_summary_from_payload(payload: Mapping[str, object]) -> RancherSettingSummary:
    """Normalize one Rancher setting payload, shaping oversized ``value`` and
    ``default`` identically (L-3a / M-SETTINGS) via the shared helper."""

    summary = RancherSettingSummary.model_validate(payload)
    shaped = _shape_setting_value(summary.value, field="value")
    shaped.update(_shape_setting_value(summary.default, field="default"))
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
