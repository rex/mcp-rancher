"""Typed models for curated kube-prometheus-stack reads.

Targets the Prometheus Operator CRDs at ``monitoring.coreos.com/v1``:
PrometheusRule (alert and recording rules), ServiceMonitor (scrape
targets via Service selector), and PodMonitor (scrape targets via Pod
selector).

Distinct from the existing ``monitoring`` pack (a single
capability-detection tool for Rancher's monitoring stack as a whole)
and from the ``alerts`` pack (Norman ``cluster_alert_rule``, the
legacy Rancher alerting system).
"""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_prometheus_rule_summaries() -> list["RancherPrometheusRuleSummary"]:
    """Return a typed empty PrometheusRule summary list."""

    return []


def _empty_service_monitor_summaries() -> list["RancherServiceMonitorSummary"]:
    """Return a typed empty ServiceMonitor summary list."""

    return []


def _empty_pod_monitor_summaries() -> list["RancherPodMonitorSummary"]:
    """Return a typed empty PodMonitor summary list."""

    return []


class _PrometheusOperatorBase(RancherModel):
    """Shared name/namespace for monitoring.coreos.com/v1 resources."""

    name: str = Field(
        default="<unknown>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )


class RancherPrometheusRuleSummary(_PrometheusOperatorBase):
    """Typed summary for one PrometheusRule."""

    group_count: int = 0
    rule_count: int = 0
    alert_count: int = 0
    recording_count: int = 0


class RancherPrometheusRuleDetail(RancherPrometheusRuleSummary):
    """Typed detail for one PrometheusRule."""

    group_names: list[str] = Field(default_factory=list)
    alert_names: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherPrometheusRuleList(RancherModel):
    """Typed list response for PrometheusRule resources in one namespace."""

    instance: str
    cluster_id: str
    namespace: str | None
    prometheus_rule_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    prometheus_rules: list[RancherPrometheusRuleSummary] = Field(
        default_factory=_empty_prometheus_rule_summaries,
    )


class RancherServiceMonitorSummary(_PrometheusOperatorBase):
    """Typed summary for one ServiceMonitor."""

    selector_match_labels: dict[str, str] = Field(
        default_factory=dict,
        validation_alias=AliasPath("spec", "selector", "matchLabels"),
    )
    endpoint_count: int = 0
    target_namespaces: list[str] = Field(default_factory=list)
    job_label: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "jobLabel"),
    )


class RancherServiceMonitorDetail(RancherServiceMonitorSummary):
    """Typed detail for one ServiceMonitor."""

    endpoint_ports: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherServiceMonitorList(RancherModel):
    """Typed list response for ServiceMonitors in one namespace."""

    instance: str
    cluster_id: str
    namespace: str | None
    service_monitor_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    service_monitors: list[RancherServiceMonitorSummary] = Field(
        default_factory=_empty_service_monitor_summaries,
    )


class RancherPodMonitorSummary(_PrometheusOperatorBase):
    """Typed summary for one PodMonitor."""

    selector_match_labels: dict[str, str] = Field(
        default_factory=dict,
        validation_alias=AliasPath("spec", "selector", "matchLabels"),
    )
    endpoint_count: int = 0
    target_namespaces: list[str] = Field(default_factory=list)
    job_label: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "jobLabel"),
    )


class RancherPodMonitorDetail(RancherPodMonitorSummary):
    """Typed detail for one PodMonitor."""

    endpoint_ports: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherPodMonitorList(RancherModel):
    """Typed list response for PodMonitors in one namespace."""

    instance: str
    cluster_id: str
    namespace: str | None
    pod_monitor_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    pod_monitors: list[RancherPodMonitorSummary] = Field(
        default_factory=_empty_pod_monitor_summaries,
    )
