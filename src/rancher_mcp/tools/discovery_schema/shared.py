# pyright: reportUnusedFunction=false
"""Shared helpers for API-plane and schema discovery tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.discovery import SchemaDetail, SchemaSummary


def _mapping_keys(payload: object) -> list[str]:
    """Return sorted keys from a mapping-like payload."""

    if not isinstance(payload, Mapping):
        return []
    return sorted(cast(Mapping[str, object], payload).keys())


def _api_version_string(payload: object) -> str | None:
    """Return a compact API version string from a Rancher root payload field."""

    if isinstance(payload, str):
        return payload
    if not isinstance(payload, Mapping):
        return None

    mapping = cast(Mapping[str, object], payload)
    raw_group = mapping.get("group")
    group = raw_group if isinstance(raw_group, str) else None
    raw_version = mapping.get("version")
    version = raw_version if isinstance(raw_version, str) else None

    if group and version:
        return f"{group}/{version}"
    return version or group


def _string_list(payload: object) -> list[str]:
    """Normalize a loose list payload into a strict string list."""

    if not isinstance(payload, list):
        return []
    items = cast(list[object], payload)
    return [str(item) for item in items]


def _schema_payloads(raw_items: object) -> list[Mapping[str, object]]:
    """Filter Rancher collection payloads down to schema mappings."""

    if not isinstance(raw_items, list):
        return []

    items = cast(list[object], raw_items)
    payloads: list[Mapping[str, object]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        mapping = cast(Mapping[str, object], item)
        if isinstance(mapping.get("id"), str):
            payloads.append(mapping)
    return payloads


def _schema_summary_from_payload(payload: Mapping[str, object]) -> SchemaSummary:
    """Normalize a Norman or Steve schema payload into a compact summary."""

    raw_plural_name = payload.get("pluralName")
    plural_name = raw_plural_name if isinstance(raw_plural_name, str) else None
    collection_methods = _string_list(payload.get("collectionMethods"))
    resource_methods = _string_list(payload.get("resourceMethods"))
    field_count = len(_mapping_keys(payload.get("resourceFields")))
    raw_id = payload.get("id")
    schema_id = raw_id if isinstance(raw_id, str) else ""
    return SchemaSummary(
        id=schema_id,
        plural_name=plural_name,
        collection_methods=collection_methods,
        resource_methods=resource_methods,
        link_keys=_mapping_keys(payload.get("links")),
        field_count=field_count,
    )


def _schema_detail_from_payload(
    *,
    instance: str,
    plane: str,
    payload: Mapping[str, object],
    cluster_id: str | None = None,
) -> SchemaDetail:
    """Normalize a Norman or Steve schema payload into detailed output."""

    summary = _schema_summary_from_payload(payload)
    return SchemaDetail(
        instance=instance,
        plane=plane,
        cluster_id=cluster_id,
        id=summary.id,
        plural_name=summary.plural_name,
        collection_methods=summary.collection_methods,
        resource_methods=summary.resource_methods,
        link_keys=summary.link_keys,
        field_keys=_mapping_keys(payload.get("resourceFields")),
        collection_filter_keys=_mapping_keys(payload.get("collectionFilters")),
    )
