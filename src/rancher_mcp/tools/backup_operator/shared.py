"""Shared normalization helpers for Rancher Backup Operator tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.backup_operator import (
    RancherBackupSummary,
    RancherRestoreSummary,
)
from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.conditions import condition_types_true, conditions_from_value
from rancher_mcp.tools.support.values import mapping_value, string_value


def _build_list_query_params(
    *,
    limit: int | None,
    continue_token: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed list query params for raw Kubernetes proxy backup-operator calls."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if continue_token is not None:
        params["continue"] = continue_token
    return params


def _items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    return object_items(payload, field="items")


def _conditions(payload: Mapping[str, object]) -> list[RancherCondition]:
    """Pull status.conditions and normalize into typed RancherCondition objects."""

    status = mapping_value(payload, "status") or {}
    return conditions_from_value(status.get("conditions"))


def _summary_state_from_payload(payload: Mapping[str, object]) -> str | None:
    """Derive a coarse summary state from status conditions."""

    conditions = _conditions(payload)
    types_true = condition_types_true(conditions)
    if "Ready" in types_true:
        return "ready"
    if "Reconciling" in types_true:
        return "reconciling"
    status = mapping_value(payload, "status") or {}
    summary = string_value(status, "summary")
    return summary


def _storage_location_summary(payload: Mapping[str, object]) -> str | None:
    """Render a one-line description of the configured storage location.

    Backup Operator uses ``spec.storageLocation`` with one of: ``s3``
    or ``default``. The ``s3`` block has ``bucketName`` + ``region`` +
    ``endpoint``; ``default`` means use the operator's controller-level
    config.
    """

    spec = mapping_value(payload, "spec") or {}
    storage = mapping_value(spec, "storageLocation") or {}
    if "default" in storage:
        return "default"
    s3 = mapping_value(storage, "s3") or {}
    bucket = string_value(s3, "bucketName")
    region = string_value(s3, "region")
    if bucket and region:
        return f"s3://{bucket} ({region})"
    if bucket:
        return f"s3://{bucket}"
    return None


def _backup_summary_from_payload(payload: Mapping[str, object]) -> RancherBackupSummary:
    """Normalize one Rancher Backup payload."""

    summary = RancherBackupSummary.model_validate(payload)
    return summary.model_copy(update={"summary_state": _summary_state_from_payload(payload)})


def _restore_summary_from_payload(payload: Mapping[str, object]) -> RancherRestoreSummary:
    """Normalize one Rancher Restore payload."""

    summary = RancherRestoreSummary.model_validate(payload)
    return summary.model_copy(update={"summary_state": _summary_state_from_payload(payload)})


backup_summary_from_payload = _backup_summary_from_payload
build_list_query_params = _build_list_query_params
condition_types_true = condition_types_true
conditions_from_payload = _conditions
items = _items
restore_summary_from_payload = _restore_summary_from_payload
storage_location_summary = _storage_location_summary
summary_state_from_payload = _summary_state_from_payload
