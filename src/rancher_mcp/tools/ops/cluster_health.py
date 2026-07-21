"""Cluster health convenience tools — single-call health diagnosis."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.models.ops.cluster_health import (
    ClusterHealthCheck,
    ClusterHealthSummary,
    ClusterIssue,
    ClustersHealthSummary,
    NodeHealthRollup,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.clusters_nodes.shared import (
    cluster_summary_from_payload,
    data_items,
    node_summary_from_payload,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.conditions import conditions_from_value
from rancher_mcp.tools.support.derive import age_days, condition_severity
from rancher_mcp.tools.support.values import status_to_bool, string_value

# Rancher cluster conditions that represent optional features or configuration
# choices — False means "not enabled", not "broken". Exclude from health issues.
_FEATURE_FLAG_CONDITIONS: frozenset[str] = frozenset(
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


def _condition_types_false(conditions: list[RancherCondition]) -> list[str]:
    """Return sorted condition types whose status is explicitly false."""

    return sorted(c.type for c in conditions if status_to_bool(c.status) is False)


def _component_health(
    payload: dict[str, object],
) -> tuple[int, int, list[str]]:
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


def _condition_counts(conditions: list[RancherCondition]) -> dict[str, int]:
    """Count conditions by truthiness — replaces the ``condition_types_true`` echo."""

    counts = {"true": 0, "false": 0, "unknown": 0}
    for condition in conditions:
        truth = status_to_bool(condition.status)
        counts["true" if truth is True else "false" if truth is False else "unknown"] += 1
    return counts


def _derive_issues(
    state: str | None,
    conditions: list[RancherCondition],
    component_unhealthy_names: list[str],
    nodes: NodeHealthRollup,
) -> list[ClusterIssue]:
    """Derive structured, severity-ranked issues from cluster health signals.

    Each condition-based issue carries its severity + ``since``/``age_days`` +
    reason/message inline (ADR-0002), so an agent branches without a second call
    and can tell a five-year-old benign state from a live incident.
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
        if condition.type in _FEATURE_FLAG_CONDITIONS:
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
            )
        )
    issues.extend(
        ClusterIssue(
            type="Component", severity="warning", message=f"Component '{name}' is unhealthy"
        )
        for name in component_unhealthy_names
    )
    if nodes.not_ready > 0:
        issues.append(
            ClusterIssue(
                type="NodesNotReady",
                severity="critical",
                message=f"{nodes.not_ready}/{nodes.total} node(s) not ready",
            )
        )
    if nodes.unschedulable > 0:
        issues.append(
            ClusterIssue(
                type="NodesUnschedulable",
                severity="warning",
                message=f"{nodes.unschedulable}/{nodes.total} node(s) unschedulable",
            )
        )
    return issues


def _rollup_nodes_by_cluster(
    cluster_id: str,
    node_items: list[dict[str, object]],
) -> NodeHealthRollup:
    """Build a node-health rollup for one cluster from Rancher node payloads."""

    node_summaries = [
        node_summary_from_payload(node)
        for node in node_items
        if string_value(node, "clusterId") == cluster_id
    ]
    return NodeHealthRollup(
        total=len(node_summaries),
        ready=sum(1 for node in node_summaries if node.ready is True),
        not_ready=sum(1 for node in node_summaries if node.ready is not True),
        unschedulable=sum(1 for node in node_summaries if node.unschedulable is True),
    )


async def _build_cluster_health(
    instance_name: str,
    cluster_id: str,
    client: ManagementDiscoveryClient,
    ctx: Context[Any, Any, Any] | None = None,
) -> ClusterHealthCheck:
    """Fetch cluster detail + nodes and produce a health diagnosis."""

    if ctx:
        await ctx.report_progress(0, 2)
    payload = await client.get_json(f"/v3/clusters/{cluster_id}")
    summary = cluster_summary_from_payload(payload)
    conditions = conditions_from_value(payload.get("conditions"))
    ct_false = _condition_types_false(conditions)
    ch, cu, cu_names = _component_health(payload)

    if ctx:
        await ctx.report_progress(1, 2)
    node_payload = await client.get_json(
        "/v3/nodes",
        params={"clusterId": cluster_id},
    )
    nodes = _rollup_nodes_by_cluster(cluster_id, data_items(node_payload))

    issues = _derive_issues(summary.state, conditions, cu_names, nodes)
    healthy = len(issues) == 0

    return ClusterHealthCheck(
        instance=instance_name,
        cluster_id=summary.id,
        cluster_name=summary.name,
        state=summary.state,
        healthy=healthy,
        kubernetes_version=summary.kubernetes_version,
        provider=summary.provider,
        conditions=conditions,
        condition_counts=_condition_counts(conditions),
        condition_types_false=ct_false,
        component_healthy_count=ch,
        component_unhealthy_count=cu,
        component_unhealthy_names=cu_names,
        nodes=nodes,
        issues=issues,
        suggested_next_steps=[
            "rancher_clusters_health_summary",
            "rancher_nodes_list",
            "rancher_pods_list",
        ],
    )


async def rancher_cluster_health_check(
    cluster_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
    ctx: Context[Any, Any, Any] | None = None,
) -> ClusterHealthCheck:
    """One-call cluster health diagnosis."""

    resolved = settings or get_settings()
    name, config = resolve_instance(resolved, instance)
    if client is not None:
        return await _build_cluster_health(name, cluster_id, client, ctx)
    async with RancherManagementClient(name, config) as mc:
        return await _build_cluster_health(name, cluster_id, mc, ctx)


async def rancher_cluster_health_check_tool(
    cluster_id: str,
    instance: str | None = None,
    ctx: Context[Any, Any, Any] | None = None,
) -> ClusterHealthCheck:
    """One-call cluster health check with conditions, components, and nodes."""

    return await rancher_cluster_health_check(
        cluster_id=cluster_id,
        instance=instance,
        ctx=ctx,
    )


async def _build_clusters_health_summary(
    instance_name: str,
    client: ManagementDiscoveryClient,
    ctx: Context[Any, Any, Any] | None = None,
) -> ClustersHealthSummary:
    """Fetch all clusters and produce a fleet-wide health rollup."""

    if ctx:
        await ctx.report_progress(0, 2)
    cluster_payload = await client.get_json("/v3/clusters")
    if ctx:
        await ctx.report_progress(1, 2)
    node_payload = await client.get_json("/v3/nodes")
    clusters_data = data_items(cluster_payload)
    all_nodes = data_items(node_payload)
    node_rollups = {
        cluster_summary_from_payload(cluster_data).id: _rollup_nodes_by_cluster(
            cluster_summary_from_payload(cluster_data).id,
            all_nodes,
        )
        for cluster_data in clusters_data
    }
    summaries: list[ClusterHealthSummary] = []
    by_severity: dict[str, int] = {}
    versions: dict[str, int] = {}

    for cluster_data in clusters_data:
        cs = cluster_summary_from_payload(cluster_data)
        conditions = conditions_from_value(cluster_data.get("conditions"))
        _ch, _cu, cu_names = _component_health(cluster_data)
        nodes = node_rollups.get(cs.id, NodeHealthRollup())

        issues = _derive_issues(cs.state, conditions, cu_names, nodes)
        healthy = len(issues) == 0
        for issue in issues:
            by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1
        if cs.kubernetes_version:
            versions[cs.kubernetes_version] = versions.get(cs.kubernetes_version, 0) + 1
        summaries.append(
            ClusterHealthSummary(
                cluster_id=cs.id,
                cluster_name=cs.name,
                state=cs.state,
                healthy=healthy,
                node_count=cs.node_count,
                nodes_ready=nodes.ready,
                nodes_not_ready=nodes.not_ready,
                issue_count=len(issues),
                top_issues=issues[:3],
            )
        )

    healthy_count = sum(1 for s in summaries if s.healthy)
    return ClustersHealthSummary(
        instance=instance_name,
        total_clusters=len(summaries),
        healthy_count=healthy_count,
        unhealthy_count=len(summaries) - healthy_count,
        by_severity=by_severity,
        versions=versions,
        clusters=summaries,
        suggested_next_steps=[
            "rancher_cluster_health_check",
            "rancher_nodes_list",
            "rancher_clusters_list",
        ],
    )


async def rancher_clusters_health_summary(
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
    ctx: Context[Any, Any, Any] | None = None,
) -> ClustersHealthSummary:
    """Estate-wide cluster health rollup across all clusters."""

    resolved = settings or get_settings()
    name, config = resolve_instance(resolved, instance)
    if client is not None:
        return await _build_clusters_health_summary(name, client, ctx)
    async with RancherManagementClient(name, config) as mc:
        return await _build_clusters_health_summary(name, mc, ctx)


async def rancher_clusters_health_summary_tool(
    instance: str | None = None,
    ctx: Context[Any, Any, Any] | None = None,
) -> ClustersHealthSummary:
    """Estate-wide cluster health summary with per-cluster health."""

    return await rancher_clusters_health_summary(instance=instance, ctx=ctx)


async def _build_cluster_nodes_summary(
    cluster_id: str,
    client: ManagementDiscoveryClient,
) -> NodeHealthRollup:
    """Fetch nodes for a cluster and produce a health rollup."""

    payload = await client.get_json(
        "/v3/nodes",
        params={"clusterId": cluster_id},
    )
    nodes = [node_summary_from_payload(n) for n in data_items(payload)]
    return NodeHealthRollup(
        total=len(nodes),
        ready=sum(1 for n in nodes if n.ready is True),
        not_ready=sum(1 for n in nodes if n.ready is not True),
        unschedulable=sum(1 for n in nodes if n.unschedulable is True),
    )


async def rancher_cluster_nodes_summary(
    cluster_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> NodeHealthRollup:
    """Per-cluster node health rollup."""

    resolved = settings or get_settings()
    name, config = resolve_instance(resolved, instance)
    if client is not None:
        return await _build_cluster_nodes_summary(cluster_id, client)
    async with RancherManagementClient(name, config) as mc:
        return await _build_cluster_nodes_summary(cluster_id, mc)


async def rancher_cluster_nodes_summary_tool(
    cluster_id: str,
    instance: str | None = None,
) -> NodeHealthRollup:
    """Per-cluster node health rollup: ready, not-ready, unschedulable."""

    return await rancher_cluster_nodes_summary(
        cluster_id=cluster_id,
        instance=instance,
    )
