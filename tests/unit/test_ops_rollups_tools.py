"""Operational rollup/summary helper tests."""

import pytest
from _ops_support import StubOpsClient, build_settings

from rancher_mcp.tools.ops.rollups import (
    rancher_namespace_workloads_summary,
    rancher_project_health_summary,
)


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
