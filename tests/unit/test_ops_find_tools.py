"""Operational failure-finder helper tests."""

import pytest
from _ops_support import StubOpsClient, build_settings

from rancher_mcp.tools.ops.find_failing_pods import rancher_find_failing_pods
from rancher_mcp.tools.ops.find_pdbs_blocking import rancher_find_pdbs_blocking
from rancher_mcp.tools.ops.find_services_no_endpoints import (
    rancher_find_services_without_endpoints,
)
from rancher_mcp.tools.ops.find_stalled_rollouts import rancher_find_stalled_rollouts
from rancher_mcp.tools.ops.find_unbound_pvcs import rancher_find_unbound_pvcs


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
