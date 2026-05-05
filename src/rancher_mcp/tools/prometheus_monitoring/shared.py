"""Shared normalization helpers for kube-prometheus-stack tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.prometheus_monitoring import (
    RancherPodMonitorSummary,
    RancherPrometheusRuleSummary,
    RancherServiceMonitorSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import mapping_value, string_list, string_value


def _build_list_query_params(
    *,
    limit: int | None,
    continue_token: str | None = None,
    label_selector: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed list query params for monitoring.coreos.com/v1 list calls."""

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


def _rule_groups(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Pull spec.groups[] from a PrometheusRule payload."""

    spec = mapping_value(payload, "spec") or {}
    raw = spec.get("groups")
    if not isinstance(raw, list):
        return []
    return [
        cast(dict[str, object], item) for item in cast(list[object], raw) if isinstance(item, dict)
    ]


def _rule_counts(payload: Mapping[str, object]) -> tuple[int, int, int, int]:
    """Return (group_count, rule_count, alert_count, recording_count)."""

    groups = _rule_groups(payload)
    rule_total = 0
    alert_total = 0
    recording_total = 0
    for group in groups:
        rules = group.get("rules")
        if not isinstance(rules, list):
            continue
        for raw_rule in cast(list[object], rules):
            if not isinstance(raw_rule, dict):
                continue
            rule = cast(dict[str, object], raw_rule)
            rule_total += 1
            if string_value(rule, "alert"):
                alert_total += 1
            if string_value(rule, "record"):
                recording_total += 1
    return len(groups), rule_total, alert_total, recording_total


def _prometheus_rule_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherPrometheusRuleSummary:
    """Normalize one PrometheusRule payload."""

    summary = RancherPrometheusRuleSummary.model_validate(payload)
    group_count, rule_count, alert_count, recording_count = _rule_counts(payload)
    return summary.model_copy(
        update={
            "group_count": group_count,
            "rule_count": rule_count,
            "alert_count": alert_count,
            "recording_count": recording_count,
        }
    )


def _group_names(payload: Mapping[str, object]) -> list[str]:
    """Return sorted unique group names from a PrometheusRule payload."""

    names = {
        string_value(group, "name")
        for group in _rule_groups(payload)
        if string_value(group, "name") is not None
    }
    return sorted(name for name in names if name is not None)


def _alert_names(payload: Mapping[str, object]) -> list[str]:
    """Return sorted unique alert names from a PrometheusRule payload."""

    alerts: set[str] = set()
    for group in _rule_groups(payload):
        rules = group.get("rules")
        if not isinstance(rules, list):
            continue
        for raw_rule in cast(list[object], rules):
            if not isinstance(raw_rule, dict):
                continue
            rule = cast(dict[str, object], raw_rule)
            alert_name = string_value(rule, "alert")
            if alert_name:
                alerts.add(alert_name)
    return sorted(alerts)


def _target_namespaces(payload: Mapping[str, object]) -> list[str]:
    """Extract spec.namespaceSelector.matchNames as a typed list."""

    spec = mapping_value(payload, "spec") or {}
    selector = mapping_value(spec, "namespaceSelector") or {}
    return string_list(selector.get("matchNames"))


def _endpoints(payload: Mapping[str, object], field: str) -> list[dict[str, object]]:
    """Pull spec.<field>[] (endpoints / podMetricsEndpoints) as typed dicts."""

    spec = mapping_value(payload, "spec") or {}
    raw = spec.get(field)
    if not isinstance(raw, list):
        return []
    return [
        cast(dict[str, object], item) for item in cast(list[object], raw) if isinstance(item, dict)
    ]


def _endpoint_ports(payload: Mapping[str, object], field: str) -> list[str]:
    """Return sorted unique port references from spec.<field>[]."""

    ports: set[str] = set()
    for endpoint in _endpoints(payload, field):
        port = string_value(endpoint, "port") or string_value(endpoint, "targetPort")
        if port:
            ports.add(port)
    return sorted(ports)


def _service_monitor_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherServiceMonitorSummary:
    """Normalize one ServiceMonitor payload."""

    summary = RancherServiceMonitorSummary.model_validate(payload)
    return summary.model_copy(
        update={
            "endpoint_count": len(_endpoints(payload, "endpoints")),
            "target_namespaces": _target_namespaces(payload),
        }
    )


def _pod_monitor_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherPodMonitorSummary:
    """Normalize one PodMonitor payload."""

    summary = RancherPodMonitorSummary.model_validate(payload)
    return summary.model_copy(
        update={
            "endpoint_count": len(_endpoints(payload, "podMetricsEndpoints")),
            "target_namespaces": _target_namespaces(payload),
        }
    )


def _service_monitor_endpoint_ports(payload: Mapping[str, object]) -> list[str]:
    """Return sorted unique port references for a ServiceMonitor (`spec.endpoints`)."""

    return _endpoint_ports(payload, "endpoints")


def _pod_monitor_endpoint_ports(payload: Mapping[str, object]) -> list[str]:
    """Return sorted unique port references for a PodMonitor (`spec.podMetricsEndpoints`)."""

    return _endpoint_ports(payload, "podMetricsEndpoints")


alert_names = _alert_names
build_list_query_params = _build_list_query_params
group_names = _group_names
items = _items
pod_monitor_endpoint_ports = _pod_monitor_endpoint_ports
pod_monitor_summary_from_payload = _pod_monitor_summary_from_payload
prometheus_rule_summary_from_payload = _prometheus_rule_summary_from_payload
service_monitor_endpoint_ports = _service_monitor_endpoint_ports
service_monitor_summary_from_payload = _service_monitor_summary_from_payload
