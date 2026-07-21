"""Typed models for Rancher alerting and notifier tools."""

from __future__ import annotations

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def _empty_notifiers() -> list[RancherNotifierSummary]:
    return []


def _empty_alert_rules() -> list[RancherAlertRuleSummary]:
    return []


def _empty_notifier_types() -> list[str]:
    return []


class RancherNotifierSummary(RancherModel):
    """Typed summary for one Rancher notifier."""

    id: str = "<unknown-notifier>"
    name: str = "<unknown-notifier>"
    cluster_id: str | None = None
    state: str | None = None
    notifier_types: list[str] = Field(default_factory=_empty_notifier_types)


class RancherNotifierDetail(RancherNotifierSummary):
    """Typed detail for one Rancher notifier."""

    status: dict[str, object] = Field(default_factory=dict)
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherNotifierList(RancherModel):
    """Typed list response for Rancher notifiers."""

    instance: str
    notifier_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    notifiers: list[RancherNotifierSummary] = Field(default_factory=_empty_notifiers)


class RancherAlertRuleSummary(RancherModel):
    """Typed summary for one Rancher cluster alert rule."""

    id: str = "<unknown-alert-rule>"
    name: str = "<unknown-alert-rule>"
    cluster_id: str | None = None
    group_id: str | None = None
    group_name: str | None = None
    severity: str | None = None
    state: str | None = None
    inherited: bool | None = None


class RancherAlertRuleDetail(RancherAlertRuleSummary):
    """Typed detail for one Rancher cluster alert rule."""

    status: dict[str, object] = Field(default_factory=dict)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherAlertRuleList(RancherModel):
    """Typed list response for Rancher cluster alert rules."""

    instance: str
    alert_rule_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    alert_rules: list[RancherAlertRuleSummary] = Field(default_factory=_empty_alert_rules)
