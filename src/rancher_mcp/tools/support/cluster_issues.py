"""Shared cluster-issue derivation (ADR-0002 / L-2b / M-A3).

Extracted from ``tools/ops/cluster_health.py`` so both the health-check
aggregate (:mod:`rancher_mcp.tools.ops.cluster_health`) and the curated
``cluster_get`` builder (:mod:`rancher_mcp.tools.clusters_nodes.shared`)
derive the exact same typed ``issues[]`` / ``condition_counts`` from a
cluster's conditions and component statuses, without one pack importing the
other. ``tools.ops.cluster_health`` already imports
``tools.clusters_nodes.shared`` (for ``cluster_summary_from_payload`` etc.),
so the reverse import would be circular; living in ``tools/support/`` (a leaf
module neither pack depends on) breaks the cycle while keeping the
derivation in exactly one place.
"""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.clusters_nodes import ClusterIssue, RancherCondition
from rancher_mcp.models.ops.cluster_health import NodeHealthRollup
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.derive import age_days, condition_severity
from rancher_mcp.tools.support.values import status_to_bool, string_value

# Rancher cluster conditions that represent optional features or configuration
# choices — False means "not enabled", not "broken". Exclude from health issues.
FEATURE_FLAG_CONDITIONS: frozenset[str] = frozenset(
    {
        "AgentTlsStrictCheck",
        "AlertingEnabled",
        "BackupEnabled",
        "CisScanEnabled",
        "IstioEnabled",
        "LoggingEnabled",
        "MonitoringEnabled",
        "OPAGatekeeperEnabled",
        "PipelineEnabled",
        "RotateCertificates",
    }
)


# Core control-plane components whose failure is critical — a down etcd,
# controller-manager, or scheduler means the cluster brain itself is failing,
# not merely a degraded add-on (M-A10 / ADR-0002 rule #2). Matched by prefix so
# Rancher's per-member names ("etcd-0", "etcd-1", ...) count as etcd too.
_CRITICAL_COMPONENT_PREFIXES: tuple[str, ...] = ("etcd", "controller-manager", "scheduler")

# Small, obviously-correct hint mapping from condition type to a short
# remediation string (M-A9 / ADR-0002 rule #4: ship the follow-up with the
# exception, no second call). Deliberately minimal — only conditions whose fix
# is unambiguous; unmapped conditions get hint=None (the base serializer drops
# a None hint from the dumped shape).
_CONDITION_HINTS: dict[str, str] = {
    "Ready": "Cluster control plane is not Ready; check node and component health.",
    "PrometheusOperatorDeployed": "The rancher-monitoring app is not installed on this cluster.",
}


def _component_issue_severity(name: str) -> str:
    """Classify a down component: etcd/controller-manager/scheduler are critical."""

    return "critical" if name.lower().startswith(_CRITICAL_COMPONENT_PREFIXES) else "warning"


def _condition_hint(condition_type: str) -> str | None:
    """Look up a short remediation hint for a known-mappable condition type."""

    return _CONDITION_HINTS.get(condition_type)


def component_health(payload: Mapping[str, object]) -> tuple[int, int, list[str]]:
    """Count healthy vs unhealthy components and return unhealthy names."""

    raw = payload.get("componentStatuses")
    if not isinstance(raw, list):
        return 0, 0, []
    healthy = 0
    unhealthy = 0
    unhealthy_names: list[str] = []
    for item in object_items(payload, field="componentStatuses"):
        name = string_value(item, "name") or "<unknown>"
        conditions = object_items(item, field="conditions")
        if not conditions:
            unhealthy += 1
            unhealthy_names.append(name)
            continue
        is_healthy = False
        for cond in conditions:
            cond_status = string_value(cond, "status")
            if cond.get("type") == "Healthy" and status_to_bool(cond_status) is True:
                is_healthy = True
                break
        if is_healthy:
            healthy += 1
        else:
            unhealthy += 1
            unhealthy_names.append(name)
    return healthy, unhealthy, sorted(unhealthy_names)


def condition_counts(conditions: list[RancherCondition]) -> dict[str, int]:
    """Count conditions by truthiness — replaces the ``condition_types_true`` echo."""

    counts = {"true": 0, "false": 0, "unknown": 0}
    for condition in conditions:
        truth = status_to_bool(condition.status)
        counts["true" if truth is True else "false" if truth is False else "unknown"] += 1
    return counts


def derive_cluster_issues(
    state: str | None,
    conditions: list[RancherCondition],
    component_unhealthy_names: list[str],
    nodes: NodeHealthRollup | None = None,
) -> list[ClusterIssue]:
    """Derive structured, severity-ranked issues from cluster health signals.

    Each condition-based issue carries its severity + ``since``/``age_days`` +
    reason/message inline (ADR-0002), so an agent branches without a second call
    and can tell a five-year-old benign state from a live incident.

    ``nodes`` is optional: ``cluster_get`` (M-A3) fetches only
    ``/v3/clusters/{id}`` (no ``/v3/nodes`` call), so it derives issues with
    ``nodes=None`` and simply skips the two node-rollup issue types below;
    ``cluster_health_check`` (L-2b) always passes a real rollup.
    """

    issues: list[ClusterIssue] = []
    if state is not None and state != "active":
        issues.append(
            ClusterIssue(
                type="ClusterState",
                severity="critical",
                message=f"Cluster state is '{state}', expected 'active'",
            )
        )
    for condition in conditions:
        if status_to_bool(condition.status) is not False:
            continue
        if condition.type in FEATURE_FLAG_CONDITIONS:
            continue
        issues.append(
            ClusterIssue(
                type=condition.type,
                status=condition.status,
                severity=condition_severity(condition.type, condition.status),
                since=condition.last_transition_time,
                age_days=age_days(condition.last_transition_time),
                reason=condition.reason,
                message=condition.message,
                hint=_condition_hint(condition.type),
            )
        )
    issues.extend(
        ClusterIssue(
            type="Component",
            severity=_component_issue_severity(name),
            message=f"Component '{name}' is unhealthy",
        )
        for name in component_unhealthy_names
    )
    if nodes is not None and nodes.not_ready > 0:
        issues.append(
            ClusterIssue(
                type="NodesNotReady",
                severity="critical",
                message=f"{nodes.not_ready}/{nodes.total} node(s) not ready",
            )
        )
    if nodes is not None and nodes.unschedulable > 0:
        issues.append(
            ClusterIssue(
                type="NodesUnschedulable",
                severity="warning",
                message=f"{nodes.unschedulable}/{nodes.total} node(s) unschedulable",
            )
        )
    return issues
