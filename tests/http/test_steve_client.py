"""HTTP-boundary tests for the Steve client."""

import httpx
import pytest
import respx
from pydantic import SecretStr

from rancher_mcp.clients.steve import RancherSteveClient
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.models.discovery import RancherInstanceConfig


def build_config() -> RancherInstanceConfig:
    """Create a deterministic instance config."""

    return RancherInstanceConfig(
        url="https://rancher.example.com",
        token=SecretStr("token-xxxxx:yyyyyyyyy"),
        verify_ssl=True,
    )


@pytest.mark.asyncio
@respx.mock
async def test_steve_client_uses_local_cluster_root() -> None:
    """Local-cluster Steve requests should target the `/v1` root."""

    route = respx.get("https://rancher.example.com/v1/schemas").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    async with RancherSteveClient("work", build_config()) as client:
        result = await client.get_json("/schemas")

    assert result == {"data": []}
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_steve_client_root_request_avoids_trailing_slash_redirect() -> None:
    """Steve root requests should target the canonical cluster root path."""

    route = respx.get("https://rancher.example.com/k8s/clusters/venue-local/v1").mock(
        return_value=httpx.Response(200, json={"type": "apiRoot"})
    )

    async with RancherSteveClient("work", build_config(), cluster_id="venue-local") as client:
        result = await client.get_json("/")

    assert result == {"type": "apiRoot"}
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_steve_client_uses_cluster_scoped_root_for_non_local_clusters() -> None:
    """Non-local Steve requests should target the Rancher cluster proxy path."""

    route = respx.get("https://rancher.example.com/k8s/clusters/venue-local/v1/schemas/pod").mock(
        return_value=httpx.Response(200, json={"id": "pod"})
    )

    async with RancherSteveClient("work", build_config(), cluster_id="venue-local") as client:
        result = await client.get_json("/schemas/pod")

    assert result == {"id": "pod"}
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_steve_client_patch_content_uses_cluster_scoped_root() -> None:
    """Raw Steve PATCH requests should preserve cluster-qualified Steve paths."""

    route = respx.patch(
        "https://rancher.example.com/k8s/clusters/venue-local/v1/configmaps/default/demo",
        params={"fieldManager": "rancher-mcp"},
    ).mock(return_value=httpx.Response(200, json={"kind": "ConfigMap"}))

    async with RancherSteveClient("work", build_config(), cluster_id="venue-local") as client:
        result = await client.patch_content_json(
            "/configmaps/default/demo",
            content='{"kind":"ConfigMap"}',
            content_type="application/apply-patch+yaml",
            params={"fieldManager": "rancher-mcp"},
        )

    assert result == {"kind": "ConfigMap"}
    assert route.called


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("method", ["post_json", "patch_json", "delete_json"])
async def test_a_read_only_instance_sends_no_mutating_request_through_steve(method: str) -> None:
    """The Steve client rides on the management client, so the read-only
    backstop there covers the Kubernetes proxy plane as well. Pinned here
    because "it happens to share the transport" is exactly the kind of fact
    that stops being true without anyone deciding it should."""

    route = respx.route().mock(return_value=httpx.Response(200, json={}))
    config = build_config().model_copy(update={"read_only": True})

    async with RancherSteveClient("work", config, cluster_id="venue-local") as client:
        with pytest.raises(RancherCapabilityError, match="read-only"):
            await getattr(client, method)("/configmaps/default/demo", payload={"k": "v"})

    assert not route.called, f"{method} reached the network on a read-only instance"
