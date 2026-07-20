"""Curated cluster/node tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.clusters_nodes import (
    rancher_cluster_get,
    rancher_clusters_list,
    rancher_node_get,
    rancher_nodes_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated cluster/node tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubManagementClient:
    """Deterministic management client for curated cluster/node tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake cluster and node payloads."""

        if path == "/v3/clusters":
            assert params == {
                "limit": 2,
                "state": "active",
                "sort": "name",
                "reverse": True,
            }
            return {
                "data": [
                    {
                        "id": "local",
                        "name": "local",
                        "displayName": "local",
                        "state": "active",
                        "provider": "imported",
                        "driver": "imported",
                        "nodeVersion": 2,
                        "version": {"gitVersion": "v1.20.15"},
                        "nodeCount": 2,
                        "capacity": {"cpu": "4", "memory": "5294864Ki"},
                        "conditions": [
                            {"type": "Ready", "status": "True"},
                            {"type": "Provisioned", "status": "True"},
                        ],
                    }
                ]
            }
        if path == "/v3/clusters/local":
            assert params is None
            return {
                "id": "local",
                "name": "local",
                "displayName": "local",
                "state": "active",
                "provider": "imported",
                "driver": "imported",
                "nodeVersion": 2,
                "version": {"gitVersion": "v1.20.15"},
                "nodeCount": 2,
                "capacity": {"cpu": "4", "memory": "5294864Ki"},
                "apiEndpoint": "https://10.96.0.1:443",
                "actions": {
                    "generateKubeconfig": "https://rancher.work.example.com/v3/clusters/local?action=generateKubeconfig"
                },
                "conditions": [
                    {"type": "Ready", "status": "True"},
                    {"type": "Provisioned", "status": "True"},
                ],
                "componentStatuses": [
                    {
                        "name": "scheduler",
                        "conditions": [{"type": "Healthy", "status": "True", "message": "ok"}],
                    }
                ],
            }
        if path == "/v3/nodes":
            assert params == {
                "clusterId": "local",
                "worker": True,
                "limit": 2,
                "sort": "name",
            }
            return {
                "data": [
                    {
                        "id": "local:machine-abc",
                        "name": "rancher-mcp-management-worker",
                        "clusterId": "local",
                        "hostname": "rancher-mcp-management-worker",
                        "state": "active",
                        "worker": True,
                        "controlPlane": False,
                        "etcd": False,
                        "unschedulable": False,
                        "ipAddress": "172.20.0.3",
                        "externalIpAddress": None,
                        "conditions": [
                            {
                                "type": "Ready",
                                "status": "True",
                                "message": "kubelet is posting ready status",
                            }
                        ],
                        "info": {"kubernetes": {"kubeletVersion": "v1.20.15"}},
                    }
                ]
            }
        if path == "/v3/nodes/local:machine-abc":
            assert params is None
            return {
                "id": "local:machine-abc",
                "name": "rancher-mcp-management-worker",
                "nodeName": "rancher-mcp-management-worker",
                "clusterId": "local",
                "hostname": "rancher-mcp-management-worker",
                "state": "active",
                "worker": True,
                "controlPlane": False,
                "etcd": False,
                "unschedulable": False,
                "ipAddress": "172.20.0.3",
                "externalIpAddress": None,
                "providerId": "kind://worker",
                "podCidr": "10.244.1.0/24",
                "capacity": {"cpu": "4", "memory": "5294864Ki", "pods": "110"},
                "allocatable": {"cpu": "4", "memory": "5294864Ki", "pods": "110"},
                "actions": {
                    "drain": "https://rancher.work.example.com/v3/nodes/local:machine-abc?action=drain"
                },
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "message": "kubelet is posting ready status",
                    }
                ],
                "info": {"kubernetes": {"kubeletVersion": "v1.20.15"}},
            }
        raise AssertionError(f"unexpected management path: {path}")


@pytest.mark.asyncio
async def test_rancher_clusters_list_returns_typed_summaries() -> None:
    """Curated clusters list should expose typed cluster summaries."""

    result = await rancher_clusters_list(
        limit=2,
        state="active",
        sort_by="name",
        reverse=True,
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.cluster_count == 1
    assert result.applied_query_params == {
        "limit": 2,
        "state": "active",
        "sort": "name",
        "reverse": True,
    }
    assert result.clusters[0].id == "local"
    assert result.clusters[0].ready is True
    # K-3: the real k8s version comes from version.gitVersion, never the
    # integer nodeVersion (which here is 2 and would coerce to "2").
    assert result.clusters[0].kubernetes_version == "v1.20.15"


@pytest.mark.asyncio
async def test_rancher_cluster_get_returns_typed_detail() -> None:
    """Curated cluster detail should expose actions, conditions, and component statuses."""

    result = await rancher_cluster_get(
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "local"
    assert result.kubernetes_version == "v1.20.15"  # K-3: version.gitVersion, not nodeVersion
    assert result.api_endpoint == "https://10.96.0.1:443"
    assert result.action_keys == ["generateKubeconfig"]
    assert result.component_statuses[0].name == "scheduler"
    assert result.component_statuses[0].healthy is True


@pytest.mark.asyncio
async def test_rancher_clusters_list_handles_empty_collection() -> None:
    """Curated clusters list should handle an empty Rancher collection cleanly."""

    class EmptyClusterClient:
        """Return an empty cluster collection."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic empty collection."""

            assert path == "/v3/clusters"
            assert params is None
            return {"data": []}

    result = await rancher_clusters_list(
        instance="work",
        settings=build_settings(),
        client=EmptyClusterClient(),
    )

    assert result.cluster_count == 0
    assert result.applied_query_params == {}
    assert result.clusters == []


@pytest.mark.asyncio
async def test_rancher_nodes_list_returns_typed_summaries() -> None:
    """Curated nodes list should expose typed node summaries."""

    result = await rancher_nodes_list(
        cluster_id="local",
        role="worker",
        limit=2,
        sort_by="name",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.node_count == 1
    assert result.applied_query_params == {
        "clusterId": "local",
        "worker": True,
        "limit": 2,
        "sort": "name",
    }
    assert result.nodes[0].id == "local:machine-abc"
    assert result.nodes[0].roles == ["worker"]
    assert result.nodes[0].ready is True


@pytest.mark.asyncio
async def test_rancher_nodes_list_filters_unready_unschedulable_nodes() -> None:
    """Curated nodes list should preserve computed readiness and role extraction."""

    class SparseNodeClient:
        """Return a node payload with computed-role and readiness edge cases."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic sparse node collection."""

            assert path == "/v3/nodes"
            assert params == {"unschedulable": True}
            return {
                "data": [
                    {
                        "id": "local:machine-drain",
                        "name": "worker-drain",
                        "state": "draining",
                        "worker": True,
                        "controlPlane": True,
                        "etcd": False,
                        "unschedulable": True,
                        "conditions": [
                            {"type": "Ready", "status": "False", "message": "draining"},
                        ],
                    }
                ]
            }

    result = await rancher_nodes_list(
        unschedulable=True,
        instance="work",
        settings=build_settings(),
        client=SparseNodeClient(),
    )

    assert result.node_count == 1
    assert result.nodes[0].ready is False
    assert result.nodes[0].roles == ["control-plane", "worker"]
    assert result.nodes[0].unschedulable is True


@pytest.mark.asyncio
async def test_rancher_node_get_returns_typed_detail() -> None:
    """Curated node detail should expose capacity, allocatable, and actions."""

    result = await rancher_node_get(
        node_id="local:machine-abc",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "local:machine-abc"
    assert result.node_name == "rancher-mcp-management-worker"
    assert result.provider_id == "kind://worker"
    assert result.cpu_capacity == "4"
    assert result.cpu_allocatable == "4"
    assert result.action_keys == ["drain"]
