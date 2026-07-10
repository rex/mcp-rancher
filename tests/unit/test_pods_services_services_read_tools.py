"""Curated service read tool tests (list + get)."""

import pytest
from _pods_services_support import StubSteveClient, build_settings

from rancher_mcp.tools.pods_services import rancher_service_get, rancher_services_list


@pytest.mark.asyncio
async def test_rancher_services_list_returns_typed_summaries() -> None:
    """Curated services list should expose typed service summaries."""

    result = await rancher_services_list(
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
    assert result.service_count == 1
    assert result.applied_query_params == {
        "limit": 2,
        "labelSelector": "app=cattle-cluster-agent",
    }
    assert result.services[0].id == "cattle-system/cattle-cluster-agent"
    assert result.services[0].service_type == "ClusterIP"


@pytest.mark.asyncio
async def test_rancher_services_list_handles_empty_collection() -> None:
    """Curated services list should handle an empty namespace collection cleanly."""

    class EmptyServiceClient:
        """Return an empty service collection."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic empty collection."""

            assert path == "/services/cattle-system"
            assert params is None
            return {"data": []}

    result = await rancher_services_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=EmptyServiceClient(),
    )

    assert result.service_count == 0
    assert result.applied_query_params == {}
    assert result.services == []


@pytest.mark.asyncio
async def test_rancher_service_get_returns_typed_detail() -> None:
    """Curated service detail should expose relationships, ports, and link keys."""

    result = await rancher_service_get(
        namespace="cattle-system",
        service_name="cattle-cluster-agent",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.id == "cattle-system/cattle-cluster-agent"
    assert result.state_name == "active"
    assert result.session_affinity == "None"
    assert result.relationship_types == [
        "discovery.k8s.io.endpointslice",
        "owner",
        "pod",
        "selects",
    ]
    assert result.ports[0].target_port == "80"
    assert "view" in result.link_keys
