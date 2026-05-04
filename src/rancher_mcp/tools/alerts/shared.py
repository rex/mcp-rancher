"""Shared normalization helpers for curated alerting and notifier tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.alerts import (
    RancherAlertRuleSummary,
    RancherNotifierSummary,
)
from rancher_mcp.tools.support.collections import object_items

_NOTIFIER_CONFIG_KEYS: tuple[str, ...] = (
    "slackConfig",
    "emailConfig",
    "pagerdutyConfig",
    "webhookConfig",
    "dingtalkConfig",
    "msteamsConfig",
    "wechatConfig",
)


def _build_notifier_query_params(
    *,
    limit: int | None,
    cluster_id: str | None,
    state: str | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher notifiers collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if state is not None:
        params["state"] = state
    return params


def _build_alert_rule_query_params(
    *,
    limit: int | None,
    cluster_id: str | None,
    severity: str | None,
    state: str | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher cluster alert rules collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if severity is not None:
        params["severity"] = severity
    if state is not None:
        params["state"] = state
    return params


def _notifier_types(payload: Mapping[str, object]) -> list[str]:
    """Extract sorted list of configured notifier types from the payload."""

    return [k.removesuffix("Config") for k in _NOTIFIER_CONFIG_KEYS if payload.get(k)]


def _notifier_summary_from_payload(payload: Mapping[str, object]) -> RancherNotifierSummary:
    """Normalize one Rancher notifier payload."""

    base = RancherNotifierSummary.model_validate(payload)
    return base.model_copy(update={"notifier_types": _notifier_types(payload)})


def _alert_rule_summary_from_payload(payload: Mapping[str, object]) -> RancherAlertRuleSummary:
    """Normalize one Rancher cluster alert rule payload."""

    return RancherAlertRuleSummary.model_validate(payload)


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher list payload."""

    return object_items(payload, field="data")


alert_rule_summary_from_payload = _alert_rule_summary_from_payload
build_alert_rule_query_params = _build_alert_rule_query_params
build_notifier_query_params = _build_notifier_query_params
data_items = _data_items
notifier_summary_from_payload = _notifier_summary_from_payload
notifier_types = _notifier_types
