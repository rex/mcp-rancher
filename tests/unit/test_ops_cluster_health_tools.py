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


def test_issue_hints_map_known_conditions_and_omit_unknown() -> None:
    """M-A9: a mapped condition type carries its remediation hint inline; an
    unmapped one gets hint=None, which the base serializer drops entirely."""

    conditions = [
        RancherCondition(type="Ready", status="False"),
        RancherCondition(type="PrometheusOperatorDeployed", status="False"),
        RancherCondition(type="Provisioned", status="False"),
    ]
    by_type = {i.type: i for i in _derive_issues("active", conditions, [], NodeHealthRollup())}

    assert (
        by_type["Ready"].hint
        == "Cluster control plane is not Ready; check node and component health."
    )
    assert (
        by_type["PrometheusOperatorDeployed"].hint
        == "The rancher-monitoring app is not installed on this cluster."
    )
    assert by_type["Provisioned"].hint is None
    assert "hint" not in by_type["Provisioned"].model_dump(by_alias=True)


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
    component_issue = next(i for i in result.issues if i.type == "Component")
    assert "controller-manager" in (component_issue.message or "")
    # M-A10: a down controller-manager is core control plane — critical, not warning.
    assert component_issue.severity == "critical"

    # M-A10: the three say-nothing component-count fields never reach the dump —
    # the unhealthy component above is the real signal, folded into issues[].
    dumped = result.model_dump(by_alias=True)
    assert "componentHealthyCount" not in dumped
    assert "componentUnhealthyCount" not in dumped
    assert "componentUnhealthyNames" not in dumped
    assert any(
        issue["type"] == "Component" and issue["severity"] == "critical"
        for issue in dumped["issues"]
    )


@pytest.mark.asyncio
async def test_healthy_cluster_health_check_dump_drops_component_count_fields() -> None:
    """M-A10: a fully healthy cluster's dump carries none of the three
    component-count fields — they collapse to nothing useful when healthy."""

    class HealthyClusterClient:
        """An all-green cluster + node payload: nothing false, nothing unhealthy."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic healthy-cluster payload."""

            if path == "/v3/clusters/healthy":
                assert params is None
                return {
                    "id": "healthy",
                    "name": "healthy",
                    "state": "active",
                    "provider": "imported",
                    "nodeVersion": "v1.28.5",
                    "conditions": [{"type": "Ready", "status": "True"}],
                    "componentStatuses": [
                        {
                            "name": "scheduler",
                            "conditions": [{"type": "Healthy", "status": "True"}],
                        },
                        {
                            "name": "controller-manager",
                            "conditions": [{"type": "Healthy", "status": "True"}],
                        },
                    ],
                }
            assert path == "/v3/nodes"
            assert params == {"clusterId": "healthy"}
            return {
                "data": [
                    {
                        "id": "healthy:worker-1",
                        "name": "worker-1",
                        "clusterId": "healthy",
                        "state": "active",
                        "worker": True,
                        "unschedulable": False,
                        "conditions": [{"type": "Ready", "status": "True"}],
                    }
                ]
            }

    result = await rancher_cluster_health_check(
        cluster_id="healthy",
        instance="work",
        settings=build_settings(),
        client=HealthyClusterClient(),
    )

    assert result.healthy is True
    assert result.issues == []
    # Attributes still populate internally — exclude=True is dump-only.
    assert result.component_healthy_count == 2
    assert result.component_unhealthy_count == 0
    assert result.component_unhealthy_names == []

    dumped = result.model_dump(by_alias=True)
    assert "componentHealthyCount" not in dumped
    assert "componentUnhealthyCount" not in dumped
    assert "componentUnhealthyNames" not in dumped


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

    # M-A8: node counts collapse into one "ready/total" token on the fleet summary.
    assert local.nodes == "1/2"
    assert edge.nodes == "1/1"

    dumped = result.model_dump(by_alias=True)
    local_dump = next(c for c in dumped["clusters"] if c["clusterId"] == "local")
    assert local_dump["nodes"] == "1/2"
    assert "nodeCount" not in local_dump
    assert "nodesReady" not in local_dump
    assert "nodesNotReady" not in local_dump


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
