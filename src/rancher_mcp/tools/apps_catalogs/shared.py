"""Shared helpers for curated app catalog tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.apps_catalogs import (
    RancherCatalogSummary,
    RancherTemplateSummary,
    RancherTemplateVersionSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.conditions import condition_types_true


def _build_catalog_query_params(
    *,
    limit: int | None,
    state: str | None,
    kind: str | None,
    helm_version: str | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher catalogs collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if state is not None:
        params["state"] = state
    if kind is not None:
        params["kind"] = kind
    if helm_version is not None:
        params["helmVersion"] = helm_version
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_template_query_params(
    *,
    limit: int | None,
    catalog_id: str | None,
    category: str | None,
    cluster_id: str | None,
    project_id: str | None,
    state: str | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher templates collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if catalog_id is not None:
        params["catalogId"] = catalog_id
    if category is not None:
        params["category"] = category
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if project_id is not None:
        params["projectId"] = project_id
    if state is not None:
        params["state"] = state
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_template_version_query_params(
    *,
    limit: int | None,
    external_id: str | None,
    version: str | None,
    version_name: str | None,
    state: str | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher template-versions collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if external_id is not None:
        params["externalId"] = external_id
    if version is not None:
        params["version"] = version
    if version_name is not None:
        params["versionName"] = version_name
    if state is not None:
        params["state"] = state
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _catalog_summary_from_payload(payload: Mapping[str, object]) -> RancherCatalogSummary:
    """Normalize one Rancher catalog payload."""

    summary = RancherCatalogSummary.model_validate(payload)
    return summary.model_copy(
        update={"condition_types_true": condition_types_true(summary.conditions)}
    )


def _template_summary_from_payload(payload: Mapping[str, object]) -> RancherTemplateSummary:
    """Normalize one Rancher template payload."""

    return RancherTemplateSummary.model_validate(payload)


def _template_version_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherTemplateVersionSummary:
    """Normalize one Rancher template-version payload."""

    summary = RancherTemplateVersionSummary.model_validate(payload)
    files = payload.get("files")
    questions = payload.get("questions")
    return summary.model_copy(
        update={
            "file_count": _collection_size(files),
            "question_count": (
                len(cast(list[object], questions)) if isinstance(questions, list) else 0
            ),
        }
    )


def _collection_size(value: object) -> int:
    """Return the size of a list-like or mapping-like value."""

    if isinstance(value, list):
        return len(cast(list[object], value))
    if isinstance(value, dict):
        return len(cast(dict[str, object], value))
    return 0


def _file_names_from_value(value: object) -> list[str]:
    """Normalize template-version file entries to a stable list of file names."""

    if isinstance(value, list):
        return [item for item in cast(list[object], value) if isinstance(item, str)]
    if isinstance(value, dict):
        return sorted(cast(dict[str, object], value).keys())
    return []


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher list payload."""

    return object_items(payload, field="data")


build_catalog_query_params = _build_catalog_query_params
build_template_query_params = _build_template_query_params
build_template_version_query_params = _build_template_version_query_params
catalog_summary_from_payload = _catalog_summary_from_payload
template_summary_from_payload = _template_summary_from_payload
template_version_summary_from_payload = _template_version_summary_from_payload
file_names_from_value = _file_names_from_value
data_items = _data_items
