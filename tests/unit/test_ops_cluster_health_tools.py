"""Operational cluster-health aggregate helper tests."""

import pytest
from _ops_support import StubOpsClient, build_settings

from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.models.ops.cluster_health import NodeHealthRollup
from rancher_mcp.tools.ops.cluster_health import (
    _derive_issues,
    rancher_cluster_health_check,
    rancher_cluster_nodes_summary,
    rancher_clusters_health_summary,
)
from rancher_mcp.tools.ops.find_unready_nodes import rancher_find_unready_nodes


def test_l2b_issues_are_severity_ranked_with_since() -> None:
    """Structured issues carry severity + since + reason; feature flags excluded."""

    conditions = [
        RancherCondition(
            type="Ready",
            status="False",
            reason="NodeDown",
            last_transition_time="2021-04-20T19:22:02Z",
        ),
        RancherCondition(type="PrometheusOperatorDeployed", status="False"),
        RancherCondition(type="MonitoringEnabled", status="False"),  # feature flag
    ]
    by_type = {i.type: i for i in _derive_issues("active", conditions, [], NodeHealthRollup())}

    assert "MonitoringEnabled" not in by_type  # cosmetic feature flag excluded
    assert by_type["Ready"].severity == "critical"
    assert by_type["Ready"].since == "2021-04-20T19:22:02Z"  # age-vs-incident signal
    assert by_type["Ready"].reason == "NodeDown"
    assert by_type["PrometheusOperatorDeployed"].severity == "warning"


@pytest.mark.asyncio
async def test_rancher_cluster_health_check_reports_component_and_node_issues() -> None:
    """Cluster health should surface false conditions, unhealthy components, and node rollups."""

    result = await rancher_cluster_health_check(
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubOpsClient(),
    )

    assert result.instance == "work"
    assert result.healthy is False
    assert result.condition_types_false == ["Provisioned"]
    assert result.component_unhealthy_names == ["controller-manager"]
    assert result.nodes.total == 2
    assert result.nodes.ready == 1
    assert result.nodes.not_ready == 1
    assert result.nodes.unschedulable == 1
    # Issues are structured now (L-2b): severity + since + reason inline.
    assert any(i.type == "Provisioned" and i.status == "False" for i in result.issues)
    assert any(
        i.type == "Component" and "controller-manager" in (i.message or "") for i in result.issues
    )


@pytest.mark.asyncio
async def test_rancher_clusters_health_summary_populates_node_rollups() -> None:
    """Fleet health summary should include per-cluster node readiness counts."""

    result = await rancher_clusters_health_summary(
        instance="work",
        settings=build_settings(),
        client=StubOpsClient(),
    )

    assert result.total_clusters == 2
    assert result.unhealthy_count == 2
    local = next(cluster for cluster in result.clusters if cluster.cluster_id == "local")
    edge = next(cluster for cluster in result.clusters if cluster.cluster_id == "edge")
    assert local.nodes_ready == 1
    assert local.nodes_not_ready == 1
    assert local.issue_count >= 1
    assert edge.nodes_ready == 1
    assert edge.nodes_not_ready == 0
    assert any(i.type == "ClusterState" for i in edge.top_issues)


@pytest.mark.asyncio
async def test_rancher_cluster_nodes_summary_and_unready_nodes_share_consistent_rollups() -> None:
    """Cluster node helpers should agree on readiness and unschedulable signals."""

    summary = await rancher_cluster_nodes_summary(
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubOpsClient(),
    )
    unready = await rancher_find_unready_nodes(
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubOpsClient(),
    )

    assert summary.total == 2
    assert summary.not_ready == 1
    assert summary.unschedulable == 1
    assert unready.unready_count == 1
    assert unready.nodes[0].name == "cp-1"
    assert unready.nodes[0].roles == ["control-plane"]
