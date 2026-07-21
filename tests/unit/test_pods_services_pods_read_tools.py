"""Curated pod read tool tests (list + get)."""

import pytest
from _pods_services_support import (
    StubEventsManagementClient,
    StubSteveClient,
    build_settings,
    patch_pod_events_client,
)

from rancher_mcp.tools.pods_services import rancher_pod_get, rancher_pods_list


@pytest.mark.asyncio
async def test_rancher_pods_list_returns_typed_summaries() -> None:
    """Curated pods list should expose typed pod summaries."""

    result = await rancher_pods_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        limit=2,
        label_selector="app=cattle-cluster-agent",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.instance == "work"
    assert result.namespace == "cattle-system"
    assert result.pod_count == 1
    assert result.applied_query_params == {
        "limit": 2,
        "labelSelector": "app=cattle-cluster-agent",
    }
    assert result.pods[0].id == "cattle-system/cattle-cluster-agent-abc"
    assert result.pods[0].ready == "1/1"
    assert result.pods[0].ready_condition is True
    assert result.pods[0].owner == "ReplicaSet/cattle-cluster-agent-rs"
    assert result.pods[0].owner_kind == "ReplicaSet"


@pytest.mark.asyncio
async def test_rancher_pod_get_returns_typed_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    """Curated pod detail should expose container and condition detail."""

    patch_pod_events_client(monkeypatch, StubEventsManagementClient())
    result = await rancher_pod_get(
        namespace="cattle-system",
        pod_name="cattle-cluster-agent-abc",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.id == "cattle-system/cattle-cluster-agent-abc"
    assert result.host_ip == "172.20.0.4"
    assert result.service_account_name == "cattle"
    assert result.containers[0].name == "cluster-register"
    assert "view" in result.link_keys
    assert result.events == []
    assert "events" not in result.model_dump(by_alias=True)


@pytest.mark.asyncio
async def test_rancher_pods_list_filters_phase_and_handles_sparse_status() -> None:
    """Curated pods list should filter on computed pod phase without crashing on sparse status."""

    class MixedPodClient:
        """Return mixed pod phases with one sparse status payload."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic pod collection."""

            assert path == "/pods/cattle-system"
            assert params is None
            return {
                "data": [
                    {
                        "id": "cattle-system/running-pod",
                        "metadata": {"name": "running-pod", "namespace": "cattle-system"},
                        "status": {"phase": "Running"},
                    },
                    {
                        "id": "cattle-system/pending-pod",
                        "metadata": {"name": "pending-pod", "namespace": "cattle-system"},
                    },
                ]
            }

    result = await rancher_pods_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        phase="Running",
        instance="work",
        settings=build_settings(),
        client=MixedPodClient(),
    )

    assert result.pod_count == 1
    assert [pod.name for pod in result.pods] == ["running-pod"]
