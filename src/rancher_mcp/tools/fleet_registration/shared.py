"""Shared helpers for curated Rancher Fleet and registration tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.fleet_registration import (
    RancherClusterRegistrationTokenSummary,
    RancherFleetWorkspaceSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import mapping_value


def _build_query_params(**values: str | int | bool | None) -> dict[str, str | int | bool]:
    """Drop unset query params while preserving typed scalar values."""

    params: dict[str, str | int | bool] = {}
    for key, value in values.items():
        if value is not None:
            params[key] = value
    return params


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher list payload."""

    return object_items(payload, field="data")


def _action_keys(payload: Mapping[str, object]) -> list[str]:
    """Return sorted Rancher action keys from a payload."""

    return sorted(mapping_value(payload, "actions") or {})


def _link_keys(payload: Mapping[str, object]) -> list[str]:
    """Return sorted Rancher link keys from a payload."""

    return sorted(mapping_value(payload, "links") or {})


def _fleet_workspace_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherFleetWorkspaceSummary:
    """Normalize one Rancher Fleet workspace payload."""

    return RancherFleetWorkspaceSummary.model_validate(payload)


def _cluster_registration_token_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherClusterRegistrationTokenSummary:
    """Normalize one Rancher cluster-registration-token payload."""

    return RancherClusterRegistrationTokenSummary.model_validate(payload)


build_query_params = _build_query_params
data_items = _data_items
action_keys = _action_keys
link_keys = _link_keys
fleet_workspace_summary_from_payload = _fleet_workspace_summary_from_payload
cluster_registration_token_summary_from_payload = _cluster_registration_token_summary_from_payload
