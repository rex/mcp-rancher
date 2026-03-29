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


def _build_query_params(**values: str | int | bool | None) -> dict[str, str | int | bool]:
    """Drop unset query params while preserving typed scalar values."""

    params: dict[str, str | int | bool] = {}
    for key, value in values.items():
        if value is not None:
            params[key] = value
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


build_query_params = _build_query_params
data_items = _data_items
action_keys = _action_keys
link_keys = _link_keys
target_types = _target_types
cluster_logging_summary_from_payload = _cluster_logging_summary_from_payload
project_logging_summary_from_payload = _project_logging_summary_from_payload
etcd_backup_summary_from_payload = _etcd_backup_summary_from_payload
