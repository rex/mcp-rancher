"""Shared normalization helpers for curated certificate-inventory tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.certificates import (
    RancherCertificateSummary,
    RancherNamespacedCertificateSummary,
)
from rancher_mcp.tools.support.collections import object_items


def _build_certificate_query_params(
    *,
    limit: int | None,
    name: str | None = None,
    state: str | None = None,
    project_id: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
) -> dict[str, str | int | bool]:
    """Build typed query params for certificate list calls."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if name is not None:
        params["name"] = name
    if state is not None:
        params["state"] = state
    if project_id is not None:
        params["projectId"] = project_id
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_namespaced_certificate_query_params(
    *,
    limit: int | None,
    name: str | None = None,
    state: str | None = None,
    namespace_id: str | None = None,
    project_id: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
) -> dict[str, str | int | bool]:
    """Build typed query params for namespaced-certificate list calls."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if name is not None:
        params["name"] = name
    if state is not None:
        params["state"] = state
    if namespace_id is not None:
        params["namespaceId"] = namespace_id
    if project_id is not None:
        params["projectId"] = project_id
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher Norman list payload."""

    return object_items(payload, field="data")


def _certificate_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherCertificateSummary:
    """Normalize one Rancher certificate payload (auto-alias handles all fields)."""

    return RancherCertificateSummary.model_validate(payload)


def _namespaced_certificate_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherNamespacedCertificateSummary:
    """Normalize one Rancher namespaced-certificate payload."""

    return RancherNamespacedCertificateSummary.model_validate(payload)


build_certificate_query_params = _build_certificate_query_params
build_namespaced_certificate_query_params = _build_namespaced_certificate_query_params
certificate_summary_from_payload = _certificate_summary_from_payload
data_items = _data_items
namespaced_certificate_summary_from_payload = _namespaced_certificate_summary_from_payload
