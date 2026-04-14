"""Operational aggregate helper tests."""

from collections.abc import Mapping

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.ops.cluster_health import (
    rancher_cluster_health_check,
    rancher_cluster_nodes_summary,
    rancher_clusters_health_summary,
)
from rancher_mcp.tools.ops.find_failing_pods import rancher_find_failing_pods
from rancher_mcp.tools.ops.find_pdbs_blocking import rancher_find_pdbs_blocking
from rancher_mcp.tools.ops.find_services_no_endpoints import (
    rancher_find_services_without_endpoints,
)
from rancher_mcp.tools.ops.find_stalled_rollouts import rancher_find_stalled_rollouts
from rancher_mcp.tools.ops.find_unbound_pvcs import rancher_find_unbound_pvcs
from rancher_mcp.tools.ops.find_unready_nodes import rancher_find_unready_nodes
from rancher_mcp.tools.ops.paths import k8s_apps_ns_path, k8s_core_ns_path, k8s_policy_ns_path
from rancher_mcp.tools.ops.rollups import (
    rancher_namespace_workloads_summary,
    rancher_project_health_summary,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for operational helper tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubOpsClient:
    """Deterministic management client for operational helper tools."""

    async def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Return fake Rancher and Kubernetes payloads for ops helpers."""

        if path == "/v3/clusters":
            assert params is None
            return {
                "data": [
                    {
                        "id": "local",
                        "name": "local",
                        "state": "active",
                        "provider": "imported",
                        "nodeVersion": "v1.20.15",
                        "nodeCount": 2,
                        "conditions": [{"type": "Ready", "status": "True"}],
                        "componentStatuses": [
                            {
                                "name": "scheduler",
                                "conditions": [{"type": "Healthy", "status": "True"}],
                            }
                        ],
                    },
                    {
                        "id": "edge",
                        "name": "edge",
                        "state": "provisioning",
                        "provider": "imported",
                        "nodeVersion": "v1.23.17",
                        "nodeCount": 1,
                        "conditions": [{"type": "Ready", "status": "False"}],
                    },
                ]
            }
        if path == "/v3/clusters/local":
            assert params is None
            return {
                "id": "local",
                "name": "local",
                "state": "active",
                "provider": "imported",
                "nodeVersion": "v1.20.15",
                "conditions": [
                    {"type": "Ready", "status": "True"},
                    {"type": "Provisioned", "status": "False"},
                ],
                "componentStatuses": [
                    {
                        "name": "scheduler",
                        "conditions": [{"type": "Healthy", "status": "True"}],
                    },
                    {
                        "name": "controller-manager",
                        "conditions": [
                            {
                                "type": "Healthy",
                                "status": "False",
                                "message": "failed health check",
                            }
                        ],
                    },
                ],
            }
        if path == "/v3/projects/local:p-ops":
            assert params is None
            return {
                "id": "local:p-ops",
                "name": "ops",
                "clusterId": "local",
                "state": "active",
            }
        if path == "/v3/namespaces":
            assert params == {"projectId": "local:p-ops"}
            return {
                "data": [
                    {"id": "local:default", "name": "default"},
                ]
            }
        if path == "/v3/nodes":
            if params == {"clusterId": "local"}:
                return {
                    "data": [
                        {
                            "id": "local:worker-1",
                            "name": "worker-1",
                            "clusterId": "local",
                            "state": "active",
                            "worker": True,
                            "unschedulable": False,
                            "conditions": [{"type": "Ready", "status": "True"}],
                        },
                        {
                            "id": "local:cp-1",
                            "name": "cp-1",
                            "clusterId": "local",
                            "state": "active",
                            "controlPlane": True,
                            "unschedulable": True,
                            "conditions": [
                                {
                                    "type": "Ready",
                                    "status": "False",
                                    "message": "node not responding",
                                }
                            ],
                        },
                    ]
                }
            assert params is None
            return {
                "data": [
                    {
                        "id": "local:worker-1",
                        "name": "worker-1",
                        "clusterId": "local",
                        "state": "active",
                        "worker": True,
                        "unschedulable": False,
                        "conditions": [{"type": "Ready", "status": "True"}],
                    },
                    {
                        "id": "local:cp-1",
                        "name": "cp-1",
                        "clusterId": "local",
                        "state": "active",
                        "controlPlane": True,
                        "unschedulable": True,
                        "conditions": [{"type": "Ready", "status": "False"}],
                    },
                    {
                        "id": "edge:worker-1",
                        "name": "edge-worker-1",
                        "clusterId": "edge",
                        "state": "active",
                        "worker": True,
                        "unschedulable": False,
                        "conditions": [{"type": "Ready", "status": "True"}],
                    },
                ]
            }

        if path == k8s_core_ns_path("local", "default", "pods"):
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "api-0",
                            "namespace": "default",
                            "ownerReferences": [{"kind": "Deployment", "name": "api"}],
                        },
                        "spec": {"nodeName": "worker-1"},
                        "status": {
                            "phase": "Running",
                            "conditions": [{"type": "Ready", "status": "False"}],
                            "containerStatuses": [{"restartCount": 2, "state": {}}],
                        },
                    },
                    {
                        "metadata": {"name": "worker-0", "namespace": "default"},
                        "spec": {"nodeName": "worker-1"},
                        "status": {
                            "phase": "Failed",
                            "reason": "Evicted",
                            "containerStatuses": [{"restartCount": 1, "state": {}}],
                        },
                    },
                    {
                        "metadata": {"name": "healthy-0", "namespace": "default"},
                        "spec": {"nodeName": "worker-1"},
                        "status": {
                            "phase": "Running",
                            "conditions": [{"type": "Ready", "status": "True"}],
                            "containerStatuses": [{"restartCount": 0, "state": {}}],
                        },
                    },
                ]
            }
        if path == k8s_core_ns_path("local", "default", "services"):
            return {
                "items": [
                    {
                        "metadata": {"name": "web", "namespace": "default"},
                        "spec": {"type": "ClusterIP", "selector": {"app": "web"}},
                    },
                    {
                        "metadata": {"name": "node-api", "namespace": "default"},
                        "spec": {"type": "NodePort", "selector": {"app": "node-api"}},
                    },
                    {
                        "metadata": {"name": "external", "namespace": "default"},
                        "spec": {"type": "ExternalName", "selector": {"app": "external"}},
                    },
                ]
            }
        if path == k8s_core_ns_path("local", "default", "endpoints"):
            return {
                "items": [
                    {
                        "metadata": {"name": "web"},
                        "subsets": [{"addresses": [{"ip": "10.42.0.10"}]}],
                    },
                    {
                        "metadata": {"name": "node-api"},
                        "subsets": [{"notReadyAddresses": [{"ip": "10.42.0.11"}]}],
                    },
                ]
            }
        if path == k8s_core_ns_path("local", "default", "persistentvolumeclaims"):
            return {
                "items": [
                    {
                        "metadata": {"name": "cache", "namespace": "default"},
                        "spec": {
                            "storageClassName": "fast",
                            "resources": {"requests": {"storage": "10Gi"}},
                        },
                        "status": {"phase": "Pending"},
                    },
                    {
                        "metadata": {"name": "db", "namespace": "default"},
                        "spec": {
                            "storageClassName": "fast",
                            "resources": {"requests": {"storage": "20Gi"}},
                        },
                        "status": {"phase": "Bound"},
                    },
                ]
            }

        if path == k8s_apps_ns_path("local", "default", "deployments"):
            return {
                "items": [
                    {
                        "metadata": {"name": "api", "namespace": "default", "generation": 3},
                        "spec": {"replicas": 2, "paused": False},
                        "status": {
                            "readyReplicas": 2,
                            "availableReplicas": 2,
                            "updatedReplicas": 2,
                            "observedGeneration": 3,
                        },
                    },
                    {
                        "metadata": {"name": "worker", "namespace": "default", "generation": 5},
                        "spec": {"replicas": 3, "paused": False},
                        "status": {
                            "readyReplicas": 1,
                            "availableReplicas": 1,
                            "updatedReplicas": 2,
                            "observedGeneration": 5,
                            "unavailableReplicas": 2,
                        },
                    },
                ]
            }
        if path == k8s_apps_ns_path("local", "default", "daemonsets"):
            return {
                "items": [
                    {
                        "metadata": {"name": "node-agent", "namespace": "default"},
                        "status": {
                            "desiredNumberScheduled": 1,
                            "numberReady": 0,
                            "updatedNumberScheduled": 0,
                        },
                    }
                ]
            }
        if path == k8s_apps_ns_path("local", "default", "statefulsets"):
            return {
                "items": [
                    {
                        "metadata": {"name": "redis", "namespace": "default"},
                        "spec": {"replicas": 1},
                        "status": {"readyReplicas": 1, "updatedReplicas": 1},
                    },
                    {
                        "metadata": {"name": "queue", "namespace": "default"},
                        "spec": {"replicas": 2},
                        "status": {"readyReplicas": 1, "updatedReplicas": 1},
                    },
                ]
            }

        if path == k8s_policy_ns_path("local", "default", "poddisruptionbudgets"):
            return {
                "items": [
                    {
                        "metadata": {"name": "api-pdb", "namespace": "default"},
                        "spec": {
                            "minAvailable": 1,
                            "selector": {"matchLabels": {"app": "api"}},
                        },
                        "status": {
                            "currentHealthy": 1,
                            "desiredHealthy": 1,
                            "disruptionsAllowed": 0,
                        },
                    },
                    {
                        "metadata": {"name": "worker-pdb", "namespace": "default"},
                        "spec": {"maxUnavailable": 1},
                        "status": {"disruptionsAllowed": 1},
                    },
                ]
            }

        raise AssertionError(f"unexpected ops path: {path} params={params}")

    async def get_text(
        self,
        path: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> str:
        """Reject text requests because ops helpers should stay on JSON endpoints."""

        raise AssertionError(f"unexpected text path: {path} params={params}")

    async def post_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Reject write requests because ops helpers are read-only."""

        raise AssertionError(f"unexpected post path: {path} payload={payload} params={params}")


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
    assert "Condition Provisioned is False" in result.issues
    assert "Component 'controller-manager' is unhealthy" in result.issues


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
    assert any("Cluster state is 'provisioning'" in issue for issue in edge.top_issues)


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


@pytest.mark.asyncio
async def test_rancher_find_failing_pods_detects_failed_and_not_ready_running_pods() -> None:
    """Failing-pod finder should catch hard failures and running-but-not-ready pods."""

    result = await rancher_find_failing_pods(
        namespace="default",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubOpsClient(),
    )

    assert result.failing_count == 2
    assert [pod.name for pod in result.pods] == ["api-0", "worker-0"]
    assert result.pods[0].reason == "NotReady"
    assert result.pods[0].owner_kind == "Deployment"
    assert result.pods[1].reason == "Evicted"


@pytest.mark.asyncio
async def test_rancher_find_stalled_rollouts_includes_deployments_and_statefulsets() -> None:
    """Stalled-rollout finder should report non-converged deployments and statefulsets."""

    result = await rancher_find_stalled_rollouts(
        namespace="default",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubOpsClient(),
    )

    assert result.stalled_count == 2
    assert {(rollout.kind, rollout.name) for rollout in result.rollouts} == {
        ("Deployment", "worker"),
        ("StatefulSet", "queue"),
    }


@pytest.mark.asyncio
async def test_rancher_find_services_without_endpoints_flags_nodeports() -> None:
    """Services-without-endpoints should still flag selector-based NodePorts."""

    result = await rancher_find_services_without_endpoints(
        namespace="default",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubOpsClient(),
    )

    assert result.count == 1
    assert result.services[0].name == "node-api"
    assert result.services[0].service_type == "NodePort"
    assert result.services[0].selector == {"app": "node-api"}


@pytest.mark.asyncio
async def test_rancher_find_unbound_pvcs_and_pdb_blockers_report_blockers() -> None:
    """Storage and disruption finder helpers should summarize blocking objects."""

    pvc_result = await rancher_find_unbound_pvcs(
        namespace="default",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubOpsClient(),
    )
    pdb_result = await rancher_find_pdbs_blocking(
        namespace="default",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubOpsClient(),
    )

    assert pvc_result.unbound_count == 1
    assert pvc_result.pvcs[0].name == "cache"
    assert pvc_result.pvcs[0].requested_storage == "10Gi"
    assert pdb_result.blocking_count == 1
    assert pdb_result.blockers[0].name == "api-pdb"
    assert pdb_result.blockers[0].min_available == "1"
    assert pdb_result.blockers[0].selector_match_labels == {"app": "api"}


@pytest.mark.asyncio
async def test_rancher_namespace_workloads_summary_aggregates_readiness() -> None:
    """Namespace workload rollup should count pods and ready controller totals."""

    result = await rancher_namespace_workloads_summary(
        namespace="default",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubOpsClient(),
    )

    assert result.pod_count == 3
    assert result.pods_running == 2
    assert result.pods_pending == 0
    assert result.pods_failed == 1
    assert result.workloads.deployments_total == 2
    assert result.workloads.deployments_ready == 1
    assert result.workloads.daemonsets_not_ready == 1
    assert result.workloads.statefulsets_ready == 1
    assert result.workloads.statefulsets_not_ready == 1


@pytest.mark.asyncio
async def test_rancher_project_health_summary_counts_all_workload_controller_families() -> None:
    """Project health should aggregate pod failure signals and all controller families."""

    result = await rancher_project_health_summary(
        project_id="local:p-ops",
        instance="work",
        settings=build_settings(),
        client=StubOpsClient(),
    )

    assert result.project_name == "ops"
    assert result.namespace_count == 1
    assert result.namespaces == ["default"]
    assert result.total_pods == 3
    assert result.failing_pods == 1
    assert result.total_workloads == 5
    assert result.unhealthy_workloads == 3
