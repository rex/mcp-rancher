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


class _AllNamespacesPodClient:
    """Stub returning failing pods across two namespaces; records the path."""

    def __init__(self) -> None:
        self.requested_path: str | None = None

    async def get_json(self, path: str) -> dict[str, object]:
        self.requested_path = path
        return {
            "items": [
                {
                    "metadata": {"name": "api-0", "namespace": "team-a"},
                    "status": {"phase": "Failed"},
                    "spec": {},
                },
                {
                    "metadata": {"name": "worker-0", "namespace": "team-b"},
                    "status": {"phase": "Failed"},
                    "spec": {},
                },
            ]
        }


class _AllNamespacesServiceClient:
    """Stub with a name collision: 'web' in two namespaces, only one backed."""

    async def get_json(self, path: str) -> dict[str, object]:
        if path.endswith("/services"):
            return {
                "items": [
                    {
                        "metadata": {"name": "web", "namespace": "team-a"},
                        "spec": {"selector": {"app": "web"}},
                    },
                    {
                        "metadata": {"name": "web", "namespace": "team-b"},
                        "spec": {"selector": {"app": "web"}},
                    },
                ]
            }
        if path.endswith("/endpoints"):
            # Only team-a/web has backing addresses; team-b/web does not.
            return {
                "items": [
                    {
                        "metadata": {"name": "web", "namespace": "team-a"},
                        "subsets": [{"addresses": [{"ip": "10.0.0.1"}]}],
                    }
                ]
            }
        raise AssertionError(f"unexpected path: {path}")


@pytest.mark.asyncio
async def test_find_failing_pods_scans_all_namespaces_when_namespace_omitted() -> None:
    """Omitting namespace triages the whole cluster and labels each pod's namespace (K-4)."""

    client = _AllNamespacesPodClient()
    result = await rancher_find_failing_pods(
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,  # type: ignore[arg-type]
    )

    # All-namespaces path: no `/namespaces/<ns>/` segment.
    assert client.requested_path == "/k8s/clusters/local/api/v1/pods"
    assert result.namespace is None
    assert result.failing_count == 2
    assert {pod.namespace for pod in result.pods} == {"team-a", "team-b"}


@pytest.mark.asyncio
async def test_find_services_all_namespaces_keys_by_namespace_and_name() -> None:
    """Across namespaces, a service matches endpoints in its OWN namespace (K-4).

    Name-only matching (the pre-K-4 bug) would see 'web' backed in team-a and
    wrongly clear team-b/web too. Keying by (namespace, name) flags only team-b.
    """

    result = await rancher_find_services_without_endpoints(
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=_AllNamespacesServiceClient(),  # type: ignore[arg-type]
    )

    assert result.namespace is None
    assert result.count == 1
    assert result.services[0].namespace == "team-b"
    assert result.services[0].name == "web"
