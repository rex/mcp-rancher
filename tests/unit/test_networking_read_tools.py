"""Curated networking read tool tests (list + get across the three resources)."""

from __future__ import annotations

import pytest
from _networking_support import (
    _ENDPOINT_SLICE_PAYLOAD,
    _INGRESS_PAYLOAD,
    StubNetworkingClient,
    build_settings,
)

from rancher_mcp.tools.networking import (
    rancher_endpoint_slice_get,
    rancher_endpoint_slices_list,
    rancher_ingress_get,
    rancher_ingresses_list,
    rancher_network_policies_list,
    rancher_network_policy_get,
)


@pytest.mark.asyncio
async def test_rancher_ingresses_list_summarizes_hosts_and_addresses() -> None:
    """List should normalize hosts (sorted unique) and load-balancer addresses."""

    result = await rancher_ingresses_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.ingress_count == 1
    [ingress] = result.ingresses
    assert ingress.name == "demo-ingress"
    assert ingress.namespace == "demo"
    assert ingress.class_name == "nginx"
    assert ingress.hosts == ["admin.example.com", "demo.example.com"]
    assert ingress.load_balancer_addresses == ["10.0.0.1", "lb.example.com"]


@pytest.mark.asyncio
async def test_rancher_ingresses_list_filters_by_class_name() -> None:
    """class_name filter should drop entries whose ingress class doesn't match."""

    result = await rancher_ingresses_list(
        namespace="demo",
        cluster_id="local",
        class_name="traefik",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.ingress_count == 0
    assert result.ingresses == []


@pytest.mark.asyncio
async def test_rancher_ingress_get_returns_detail_with_annotations() -> None:
    """Detail should expose annotation_keys, hosts, payload."""

    result = await rancher_ingress_get(
        namespace="demo",
        ingress_name="demo-ingress",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.name == "demo-ingress"
    assert result.hosts == ["admin.example.com", "demo.example.com"]
    assert result.load_balancer_addresses == ["10.0.0.1", "lb.example.com"]
    assert result.annotation_keys == ["nginx.ingress.kubernetes.io/rewrite-target"]
    assert result.payload == _INGRESS_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_network_policies_list_counts_ingress_and_egress_rules() -> None:
    """List should count ingress and egress rules from spec."""

    result = await rancher_network_policies_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.network_policy_count == 1
    [policy] = result.network_policies
    assert policy.name == "deny-all"
    assert policy.policy_types == ["Ingress", "Egress"]
    assert policy.pod_selector_match_labels == {"role": "db"}
    assert policy.ingress_rule_count == 1
    assert policy.egress_rule_count == 2


@pytest.mark.asyncio
async def test_rancher_network_policy_get_returns_detail() -> None:
    """Detail should expose annotation_keys + payload + summary fields."""

    result = await rancher_network_policy_get(
        namespace="demo",
        network_policy_name="deny-all",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.name == "deny-all"
    assert result.ingress_rule_count == 1
    assert result.egress_rule_count == 2
    assert result.annotation_keys == ["description"]


@pytest.mark.asyncio
async def test_rancher_endpoint_slices_list_counts_ports_and_endpoints() -> None:
    """List should count ports, total endpoints, and ready endpoints."""

    result = await rancher_endpoint_slices_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.endpoint_slice_count == 1
    [slice_] = result.endpoint_slices
    assert slice_.name == "demo-slice"
    assert slice_.address_type == "IPv4"
    assert slice_.target_service == "demo"
    assert slice_.port_count == 2
    assert slice_.endpoint_count == 3
    assert slice_.ready_endpoint_count == 2


@pytest.mark.asyncio
async def test_rancher_endpoint_slice_get_returns_detail() -> None:
    """Detail should expose summary fields plus payload."""

    result = await rancher_endpoint_slice_get(
        namespace="demo",
        endpoint_slice_name="demo-slice",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.name == "demo-slice"
    assert result.address_type == "IPv4"
    assert result.target_service == "demo"
    assert result.port_count == 2
    assert result.endpoint_count == 3
    assert result.ready_endpoint_count == 2
    assert result.annotation_keys == []
    assert result.payload == _ENDPOINT_SLICE_PAYLOAD
