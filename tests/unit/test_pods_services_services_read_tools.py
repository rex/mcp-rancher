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

    # M-A1: the dumped count key is uniform `count`, never `serviceCount`;
    # the named collection key (`services`) stays as-is.
    dumped = result.model_dump(by_alias=True)
    assert dumped["count"] == 1
    assert "serviceCount" not in dumped
    assert "services" in dumped


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
async def test_rancher_services_list_is_cluster_wide_when_namespace_omitted() -> None:
    """Omitting `namespace` must query the cluster-wide Steve collection path
    (no namespace segment), and each service must keep its own namespace."""

    class ClusterWideServiceClient:
        """Return services spanning multiple namespaces from the all-namespaces path."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            assert path == "/services"
            return {
                "data": [
                    {
                        "metadata": {"name": "cattle-cluster-agent", "namespace": "cattle-system"},
                        "spec": {"type": "ClusterIP"},
                    },
                    {
                        "metadata": {"name": "kubernetes", "namespace": "default"},
                        "spec": {"type": "ClusterIP"},
                    },
                ]
            }

    result = await rancher_services_list(
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=ClusterWideServiceClient(),
    )

    assert result.namespace is None
    assert result.service_count == 2
    assert {service.namespace for service in result.services} == {"cattle-system", "default"}


@pytest.mark.asyncio
async def test_rancher_services_list_surfaces_load_balancer_ingress() -> None:
    """FIX 3: a LoadBalancer service's assigned external address must appear
    on the list summary — both the cloud-LB `ip` form and the AWS-ELB
    `hostname` form, and multiple ingress entries."""

    class LoadBalancerServiceClient:
        """Return one LoadBalancer service with a two-entry ingress list."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            assert path == "/services/venue"
            return {
                "data": [
                    {
                        "metadata": {"name": "front-door", "namespace": "venue"},
                        "spec": {"type": "LoadBalancer", "clusterIP": "10.96.1.1"},
                        "status": {
                            "loadBalancer": {
                                "ingress": [
                                    {"ip": "203.0.113.10"},
                                    {"hostname": "front-door.us-east-1.elb.amazonaws.com"},
                                ]
                            }
                        },
                    }
                ]
            }

    result = await rancher_services_list(
        namespace="venue",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=LoadBalancerServiceClient(),
    )

    ingress = result.services[0].load_balancer_ingress
    assert len(ingress) == 2
    assert ingress[0].ip == "203.0.113.10"
    assert ingress[0].hostname is None
    assert ingress[1].ip is None
    assert ingress[1].hostname == "front-door.us-east-1.elb.amazonaws.com"


@pytest.mark.asyncio
async def test_rancher_services_list_omits_load_balancer_ingress_for_cluster_ip() -> None:
    """FIX 3: a non-LoadBalancer service must NOT emit `loadBalancerIngress`
    noise — the field is absent from the dump, not an empty list."""

    result = await rancher_services_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        limit=2,
        label_selector="app=cattle-cluster-agent",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.services[0].load_balancer_ingress == []
    dumped = result.model_dump(by_alias=True)
    assert "loadBalancerIngress" not in dumped["services"][0]


@pytest.mark.asyncio
async def test_rancher_service_get_surfaces_load_balancer_ingress() -> None:
    """FIX 3: the get/detail shape must ALSO carry the assigned external
    address (this is the primary ask — detail is where an operator lands
    after the list points at one service)."""

    class LoadBalancerServiceDetailClient:
        """Return one LoadBalancer service detail payload."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            assert path == "/services/venue/front-door"
            return {
                "metadata": {"name": "front-door", "namespace": "venue"},
                "spec": {"type": "LoadBalancer", "clusterIP": "10.96.1.1", "ports": []},
                "status": {"loadBalancer": {"ingress": [{"ip": "203.0.113.10"}]}},
            }

    result = await rancher_service_get(
        namespace="venue",
        service_name="front-door",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=LoadBalancerServiceDetailClient(),
    )

    assert len(result.load_balancer_ingress) == 1
    assert result.load_balancer_ingress[0].ip == "203.0.113.10"


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
