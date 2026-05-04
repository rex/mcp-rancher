"""Shared helpers for curated Rancher logging and backup tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.logging_backups import (
    RancherClusterLoggingSummary,
    RancherEtcdBackupSummary,
    RancherProjectLoggingSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import mapping_value

_TARGET_FIELDS = {
    "customTargetConfig": "custom",
    "elasticsearchConfig": "elasticsearch",
    "fluentForwarderConfig": "fluent_forwarder",
    "kafkaConfig": "kafka",
    "splunkConfig": "splunk",
    "syslogConfig": "syslog",
}


def _build_cluster_logging_query_params(
    *,
    limit: int | None,
    cluster_id: str | None,
    name: str | None,
    state: str | None,
    enable_json_parsing: bool | None,
    include_system_component: bool | None,
    output_flush_interval: int | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher cluster-logging collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if name is not None:
        params["name"] = name
    if state is not None:
        params["state"] = state
    if enable_json_parsing is not None:
        params["enableJSONParsing"] = enable_json_parsing
    if include_system_component is not None:
        params["includeSystemComponent"] = include_system_component
    if output_flush_interval is not None:
        params["outputFlushInterval"] = output_flush_interval
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_project_logging_query_params(
    *,
    limit: int | None,
    project_id: str | None,
    name: str | None,
    state: str | None,
    enable_json_parsing: bool | None,
    output_flush_interval: int | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher project-logging collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if project_id is not None:
        params["projectId"] = project_id
    if name is not None:
        params["name"] = name
    if state is not None:
        params["state"] = state
    if enable_json_parsing is not None:
        params["enableJSONParsing"] = enable_json_parsing
    if output_flush_interval is not None:
        params["outputFlushInterval"] = output_flush_interval
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_etcd_backup_query_params(
    *,
    limit: int | None,
    cluster_id: str | None,
    filename: str | None,
    manual: bool | None,
    name: str | None,
    state: str | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher etcd-backup collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if filename is not None:
        params["filename"] = filename
    if manual is not None:
        params["manual"] = manual
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


def _target_types(payload: Mapping[str, object]) -> list[str]:
    """Return the configured logging target kinds present on a payload."""

    targets: list[str] = []
    for field_name, label in _TARGET_FIELDS.items():
        value = payload.get(field_name)
        if isinstance(value, Mapping) and value:
            targets.append(label)
    return targets


def _cluster_logging_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherClusterLoggingSummary:
    """Normalize one Rancher cluster-logging payload."""

    return RancherClusterLoggingSummary.model_validate(payload)


def _project_logging_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherProjectLoggingSummary:
    """Normalize one Rancher project-logging payload."""

    return RancherProjectLoggingSummary.model_validate(payload)


def _etcd_backup_summary_from_payload(payload: Mapping[str, object]) -> RancherEtcdBackupSummary:
    """Normalize one Rancher etcd-backup payload."""

    return RancherEtcdBackupSummary.model_validate(payload)


action_keys = _action_keys
build_cluster_logging_query_params = _build_cluster_logging_query_params
build_etcd_backup_query_params = _build_etcd_backup_query_params
build_project_logging_query_params = _build_project_logging_query_params
cluster_logging_summary_from_payload = _cluster_logging_summary_from_payload
data_items = _data_items
etcd_backup_summary_from_payload = _etcd_backup_summary_from_payload
link_keys = _link_keys
project_logging_summary_from_payload = _project_logging_summary_from_payload
status_keys = _status_keys
target_types = _target_types
