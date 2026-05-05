"""Shared normalization helpers for curated provisioning tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.provisioning import (
    RancherCloudCredentialSummary,
    RancherClusterDriverSummary,
    RancherNodeDriverSummary,
    RancherNodeTemplateSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import string_dict

_CREDENTIAL_CONFIG_SUFFIX = "credentialConfig"


def _build_driver_query_params(
    *,
    limit: int | None,
    active: bool | None = None,
    name: str | None = None,
    state: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
) -> dict[str, str | int | bool]:
    """Build typed query params for cluster_drivers and node_drivers list calls."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if active is not None:
        params["active"] = active
    if name is not None:
        params["name"] = name
    if state is not None:
        params["state"] = state
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_cloud_credential_query_params(
    *,
    limit: int | None,
    name: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
) -> dict[str, str | int | bool]:
    """Build typed query params for cloud_credentials list calls."""

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


def _build_node_template_query_params(
    *,
    limit: int | None,
    driver: str | None = None,
    cloud_credential_id: str | None = None,
    name: str | None = None,
    state: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
) -> dict[str, str | int | bool]:
    """Build typed query params for node_templates list calls."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if driver is not None:
        params["driver"] = driver
    if cloud_credential_id is not None:
        params["cloudCredentialId"] = cloud_credential_id
    if name is not None:
        params["name"] = name
    if state is not None:
        params["state"] = state
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher Norman list payload."""

    return object_items(payload, field="data")


def _detect_credential_driver(payload: Mapping[str, object]) -> str | None:
    """Return the driver prefix for the first ``*credentialConfig`` key found."""

    for key in payload:
        if key.endswith(_CREDENTIAL_CONFIG_SUFFIX):
            prefix = key[: -len(_CREDENTIAL_CONFIG_SUFFIX)]
            if prefix:
                return prefix
    return None


def _credential_config_field_keys(payload: Mapping[str, object]) -> list[str]:
    """Return sorted unique field names inside the ``*credentialConfig`` subkey.

    Values are intentionally not returned — the curated tool masks them.
    """

    keys: set[str] = set()
    for key, value in payload.items():
        if not key.endswith(_CREDENTIAL_CONFIG_SUFFIX):
            continue
        if not isinstance(value, dict):
            continue
        keys.update(string_dict(cast(dict[str, object], value)))
    return sorted(keys)


def _cluster_driver_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherClusterDriverSummary:
    """Normalize one cluster-driver payload."""

    return RancherClusterDriverSummary.model_validate(payload)


def _node_driver_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherNodeDriverSummary:
    """Normalize one node-driver payload."""

    return RancherNodeDriverSummary.model_validate(payload)


def _cloud_credential_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherCloudCredentialSummary:
    """Normalize one cloud-credential payload — driver detected, values masked."""

    summary = RancherCloudCredentialSummary.model_validate(payload)
    return summary.model_copy(update={"driver": _detect_credential_driver(payload)})


def _node_template_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherNodeTemplateSummary:
    """Normalize one node-template payload (auto-alias handles cloud_credential_id)."""

    return RancherNodeTemplateSummary.model_validate(payload)


build_cloud_credential_query_params = _build_cloud_credential_query_params
build_driver_query_params = _build_driver_query_params
build_node_template_query_params = _build_node_template_query_params
cloud_credential_summary_from_payload = _cloud_credential_summary_from_payload
cluster_driver_summary_from_payload = _cluster_driver_summary_from_payload
credential_config_field_keys = _credential_config_field_keys
data_items = _data_items
node_driver_summary_from_payload = _node_driver_summary_from_payload
node_template_summary_from_payload = _node_template_summary_from_payload
