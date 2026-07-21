"""Shared helpers for curated Rancher Fleet and registration tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.fleet_registration import (
    MANIFEST_URL_REDACTED,
    RancherClusterRegistrationTokenSummary,
    RancherFleetWorkspaceSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import mapping_value


def _build_fleet_workspace_query_params(
    *,
    limit: int | None,
    name: str | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher Fleet workspaces collection."""

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


def _build_cluster_registration_token_query_params(
    *,
    limit: int | None,
    cluster_id: str | None,
    name: str | None,
    state: str | None,
    namespace_id: str | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the cluster-registration-tokens collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if name is not None:
        params["name"] = name
    if state is not None:
        params["state"] = state
    if namespace_id is not None:
        params["namespaceId"] = namespace_id
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
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


def _status_keys(payload: Mapping[str, object]) -> list[str]:
    """Return sorted status field names from a Rancher payload."""

    return sorted((mapping_value(payload, "status") or {}).keys())


def _fleet_workspace_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherFleetWorkspaceSummary:
    """Normalize one Rancher Fleet workspace payload."""

    return RancherFleetWorkspaceSummary.model_validate(payload)


def _cluster_registration_token_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherClusterRegistrationTokenSummary:
    """Normalize one Rancher cluster-registration-token payload.

    Redact-don't-delete (L-0b): ``manifest_url`` is *always* overwritten with a
    marker (or ``None``), so the real join token — which the payload embeds in
    the manifest path — can never reach the list, while a present manifest is
    still signalled.
    """

    summary = RancherClusterRegistrationTokenSummary.model_validate(payload)
    has_manifest = bool(payload.get("manifestUrl"))
    return summary.model_copy(
        update={"manifest_url": MANIFEST_URL_REDACTED if has_manifest else None},
    )


action_keys = _action_keys
build_cluster_registration_token_query_params = _build_cluster_registration_token_query_params
build_fleet_workspace_query_params = _build_fleet_workspace_query_params
cluster_registration_token_summary_from_payload = _cluster_registration_token_summary_from_payload
data_items = _data_items
fleet_workspace_summary_from_payload = _fleet_workspace_summary_from_payload
link_keys = _link_keys
status_keys = _status_keys
