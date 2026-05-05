"""Shared normalization helpers for curated Longhorn tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.longhorn import (
    RancherLonghornBackupSummary,
    RancherLonghornNodeSummary,
    RancherLonghornSnapshotSummary,
    RancherLonghornVolumeSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import (
    int_value,
    mapping_value,
    string_value,
)


def _build_list_query_params(
    *,
    limit: int | None,
    continue_token: str | None = None,
    label_selector: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed list query params for Longhorn list calls."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if continue_token is not None:
        params["continue"] = continue_token
    if label_selector is not None:
        params["labelSelector"] = label_selector
    return params


def _items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    return object_items(payload, field="items")


def _volume_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherLonghornVolumeSummary:
    """Normalize one Longhorn Volume payload."""

    return RancherLonghornVolumeSummary.model_validate(payload)


def _node_ready_from_conditions(payload: Mapping[str, object]) -> bool | None:
    """Derive node readiness from status.conditions[Ready]."""

    status = mapping_value(payload, "status") or {}
    raw_conditions = status.get("conditions")
    if not isinstance(raw_conditions, list):
        return None
    for raw_cond in cast(list[object], raw_conditions):
        if not isinstance(raw_cond, dict):
            continue
        cond = cast(dict[str, object], raw_cond)
        if string_value(cond, "type") == "Ready":
            return string_value(cond, "status") == "True"
    return None


def _node_schedulable_from_conditions(payload: Mapping[str, object]) -> bool | None:
    """Derive node schedulability from status.conditions[Schedulable]."""

    status = mapping_value(payload, "status") or {}
    raw_conditions = status.get("conditions")
    if not isinstance(raw_conditions, list):
        return None
    for raw_cond in cast(list[object], raw_conditions):
        if not isinstance(raw_cond, dict):
            continue
        cond = cast(dict[str, object], raw_cond)
        if string_value(cond, "type") == "Schedulable":
            return string_value(cond, "status") == "True"
    return None


def _disk_status_map(payload: Mapping[str, object]) -> dict[str, dict[str, object]]:
    """Extract status.diskStatus as a typed dict, or empty when absent."""

    status = mapping_value(payload, "status") or {}
    raw = status.get("diskStatus")
    if not isinstance(raw, dict):
        return {}
    typed: dict[str, dict[str, object]] = {}
    for key, value in cast(dict[str, object], raw).items():
        if isinstance(value, dict):
            typed[key] = cast(dict[str, object], value)
    return typed


def _node_summary_from_payload(payload: Mapping[str, object]) -> RancherLonghornNodeSummary:
    """Normalize one Longhorn Node payload — derive ready / schedulable / disk_count."""

    summary = RancherLonghornNodeSummary.model_validate(payload)
    disks = _disk_status_map(payload)
    return summary.model_copy(
        update={
            "ready": _node_ready_from_conditions(payload),
            "schedulable": _node_schedulable_from_conditions(payload),
            "disk_count": len(disks),
        }
    )


def _node_storage_totals(payload: Mapping[str, object]) -> tuple[int | None, int | None]:
    """Return (available_total, maximum_total) summed across status.diskStatus disks."""

    disks = _disk_status_map(payload)
    if not disks:
        return None, None
    available = 0
    maximum = 0
    for disk in disks.values():
        d_available = int_value(disk, "storageAvailable")
        d_maximum = int_value(disk, "storageMaximum")
        if d_available is not None:
            available += d_available
        if d_maximum is not None:
            maximum += d_maximum
    return available, maximum


def _backup_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherLonghornBackupSummary:
    """Normalize one Longhorn Backup payload."""

    return RancherLonghornBackupSummary.model_validate(payload)


def _snapshot_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherLonghornSnapshotSummary:
    """Normalize one Longhorn Snapshot payload."""

    return RancherLonghornSnapshotSummary.model_validate(payload)


backup_summary_from_payload = _backup_summary_from_payload
build_list_query_params = _build_list_query_params
items = _items
node_storage_totals = _node_storage_totals
node_summary_from_payload = _node_summary_from_payload
snapshot_summary_from_payload = _snapshot_summary_from_payload
volume_summary_from_payload = _volume_summary_from_payload
