"""Shared helpers for curated auth and identity tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.auth_identity import (
    RancherAuthConfigSummary,
    RancherGroupSummary,
    RancherUserSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.conditions import condition_types_true


def _build_user_query_params(
    *,
    limit: int | None,
    state: str | None,
    enabled: bool | None,
    me: bool | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher users collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if state is not None:
        params["state"] = state
    if enabled is not None:
        params["enabled"] = enabled
    if me is not None:
        params["me"] = me
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_group_query_params(
    *,
    limit: int | None,
    name: str | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher groups collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if name is not None:
        params["name"] = name
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_auth_config_query_params(
    *,
    limit: int | None,
    enabled: bool | None,
    provider_type: str | None,
    access_mode: str | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher auth-config collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if enabled is not None:
        params["enabled"] = enabled
    if provider_type is not None:
        params["type"] = provider_type
    if access_mode is not None:
        params["accessMode"] = access_mode
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _user_summary_from_payload(payload: Mapping[str, object]) -> RancherUserSummary:
    """Normalize one Rancher user payload."""

    return RancherUserSummary.model_validate(payload)


def _group_summary_from_payload(payload: Mapping[str, object]) -> RancherGroupSummary:
    """Normalize one Rancher group payload."""

    return RancherGroupSummary.model_validate(payload)


def _auth_config_summary_from_payload(payload: Mapping[str, object]) -> RancherAuthConfigSummary:
    """Normalize one Rancher auth-config payload."""

    return RancherAuthConfigSummary.model_validate(payload)


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher list payload."""

    return object_items(payload, field="data")


build_auth_config_query_params = _build_auth_config_query_params
build_group_query_params = _build_group_query_params
build_user_query_params = _build_user_query_params
user_summary_from_payload = _user_summary_from_payload
group_summary_from_payload = _group_summary_from_payload
auth_config_summary_from_payload = _auth_config_summary_from_payload
data_items = _data_items
condition_types_true_sorted = condition_types_true
