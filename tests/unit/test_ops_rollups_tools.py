"""Operational rollup/summary helper tests."""

from collections.abc import Mapping

import pytest
from _ops_support import StubOpsClient, build_settings

from rancher_mcp.tools.ops.paths import k8s_apps_ns_path, k8s_core_ns_path
from rancher_mcp.tools.ops.rollups import (
    rancher_namespace_workloads_summary,
    rancher_project_health_summary,
)


@pytest.mark.asyncio
async def test_rancher_namespace_workloads_summary_aggregates_readiness() -> None:
    """Namespace workload rollup should count pods and ready controller totals.

    The shared ``default`` pod fixture's ``api-0`` is phase ``Running`` but its
    ``Ready`` condition is ``False`` — M-A4 routes pod counting through the same
    ``classify_pod_health`` helper as ``RancherPodList.summary`` (L-2c), so that
    pod now correctly lands in ``pods_failed`` (unhealthy) instead of silently
    inflating ``pods_running``.
    """

    result = await rancher_namespace_workloads_summary(
        namespace="default",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubOpsClient(),
    )

    assert result.pod_count == 3
    assert result.pods_running == 1
    assert result.pods_pending == 0
    assert result.pods_failed == 2
    assert result.pods_succeeded == 0
    assert result.workloads.deployments_total == 2
    assert result.workloads.deployments_ready == 1
    assert result.workloads.daemonsets_not_ready == 1
    assert result.workloads.statefulsets_ready == 1
    assert result.workloads.statefulsets_not_ready == 1


@pytest.mark.asyncio
async def test_rancher_project_health_summary_counts_all_workload_controller_families() -> None:
    """Project health should aggregate pod failure signals and all controller families.

    Same shared fixture and same M-A4 reclassification as the namespace test
    above: the running-but-not-ready ``api-0`` now counts as failing.
    """

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
    assert result.failing_pods == 2
    assert result.succeeded_pods == 0
    assert result.total_workloads == 5
    assert result.unhealthy_workloads == 3


class _JobsPodMixClient:
    """Minimal management-client stub: one namespace mixing live Running pods
    with terminal Succeeded (completed Job) pods and no workload controllers.

    Deliberately isolated from the shared ``StubOpsClient`` fixture so the
    M-A4 succeeded/failing split can be asserted without touching the
    fixture other test modules also depend on.
    """

    def __init__(self, *, cluster_id: str, namespace: str, project_id: str | None = None) -> None:
        self._cluster_id = cluster_id
        self._namespace = namespace
        self._project_id = project_id

    async def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Return a fixed pod mix for the configured namespace, plus empty
        workload-controller lists and (when a project is configured) the
        project/namespace-lookup payloads ``_build_project_health`` needs."""

        if path == k8s_core_ns_path(self._cluster_id, self._namespace, "pods"):
            running_pods = [
                {
                    "metadata": {"name": f"web-{i}", "namespace": self._namespace},
                    "status": {
                        "phase": "Running",
                        "conditions": [{"type": "Ready", "status": "True"}],
                    },
                }
                for i in range(3)
            ]
            succeeded_pods = [
                {
                    "metadata": {"name": f"migrate-{i}", "namespace": self._namespace},
                    "status": {"phase": "Succeeded"},
                }
                for i in range(3)
            ]
            return {"items": running_pods + succeeded_pods}
        if path in (
            k8s_apps_ns_path(self._cluster_id, self._namespace, "deployments"),
            k8s_apps_ns_path(self._cluster_id, self._namespace, "daemonsets"),
            k8s_apps_ns_path(self._cluster_id, self._namespace, "statefulsets"),
        ):
            return {"items": []}
        if self._project_id is not None:
            if path == f"/v3/projects/{self._project_id}":
                return {
                    "id": self._project_id,
                    "name": "jobs",
                    "clusterId": self._cluster_id,
                    "state": "active",
                }
            if path == f"/k8s/clusters/{self._cluster_id}/api/v1/namespaces":
                return {"items": [{"metadata": {"name": self._namespace}}]}
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
async def test_rancher_namespace_workloads_summary_excludes_succeeded_pods() -> None:
    """Completed Job pods count as pods_succeeded, never as running/pending/
    failed (M-A4) — pod_count still includes them so the total stays true."""

    result = await rancher_namespace_workloads_summary(
        namespace="jobs",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=_JobsPodMixClient(cluster_id="local", namespace="jobs"),
    )

    assert result.pod_count == 6
    assert result.pods_succeeded == 3
    assert result.pods_running == 3
    assert result.pods_pending == 0
    assert result.pods_failed == 0


@pytest.mark.asyncio
async def test_rancher_project_health_summary_excludes_succeeded_pods() -> None:
    """Completed Job pods count as succeeded_pods and never inflate
    failing_pods at the project level (M-A4) — total_pods still includes them."""

    result = await rancher_project_health_summary(
        project_id="local:p-jobs",
        instance="work",
        settings=build_settings(),
        client=_JobsPodMixClient(cluster_id="local", namespace="jobs", project_id="local:p-jobs"),
    )

    assert result.total_pods == 6
    assert result.succeeded_pods == 3
    assert result.failing_pods == 0
