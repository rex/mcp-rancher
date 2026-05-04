"""Shared helpers for curated CIS compliance tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.compliance import (
    RancherCisScanProfileSummary,
    RancherCisScanSummary,
)
from rancher_mcp.tools.support.collections import object_items


def _build_cis_scan_profile_query_params(
    *,
    limit: int | None,
    cluster_id: str | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher CIS scan profiles collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    return params


def _build_cis_scan_query_params(
    *,
    limit: int | None,
    cluster_id: str | None,
    state: str | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher CIS scans collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if state is not None:
        params["state"] = state
    return params


def _cis_scan_profile_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherCisScanProfileSummary:
    """Normalize one Rancher CIS scan profile payload."""

    return RancherCisScanProfileSummary.model_validate(payload)


def _cis_scan_summary_from_payload(payload: Mapping[str, object]) -> RancherCisScanSummary:
    """Normalize one Rancher CIS scan run payload."""

    return RancherCisScanSummary.model_validate(payload)


def _tests_from_payload(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed test entries from a CIS scan profile payload."""

    return object_items(payload, field="tests")


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher list payload."""

    return object_items(payload, field="data")


build_cis_scan_profile_query_params = _build_cis_scan_profile_query_params
build_cis_scan_query_params = _build_cis_scan_query_params
cis_scan_profile_summary_from_payload = _cis_scan_profile_summary_from_payload
cis_scan_summary_from_payload = _cis_scan_summary_from_payload
data_items = _data_items
tests_from_payload = _tests_from_payload
