"""HTTP-boundary tests for the management client."""

import httpx
import pytest
import respx
from pydantic import SecretStr

from rancher_mcp.clients.management import RancherManagementClient
from rancher_mcp.exceptions import RancherNotFoundError
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
async def test_get_text_sends_bearer_auth_header() -> None:
    """Text requests should include bearer auth and return response text."""

    route = respx.get("https://rancher.example.com/healthz").mock(
        return_value=httpx.Response(200, text="ok")
    )

    async with RancherManagementClient("work", build_config()) as client:
        result = await client.get_text("/healthz")

    assert result == "ok"
    assert route.called
    assert route.calls.last.request.headers["Authorization"].startswith("Bearer ")


@pytest.mark.asyncio
@respx.mock
async def test_get_json_maps_not_found_error() -> None:
    """JSON requests should map 404 responses into typed exceptions."""

    respx.get("https://rancher.example.com/v3/settings/server-version").mock(
        return_value=httpx.Response(404, json={"message": "missing"})
    )

    async with RancherManagementClient("work", build_config()) as client:
        with pytest.raises(RancherNotFoundError):
            await client.get_json("/v3/settings/server-version")


@pytest.mark.asyncio
@respx.mock
async def test_post_json_sends_payload_and_auth_header() -> None:
    """JSON POST requests should include bearer auth and return decoded payloads."""

    route = respx.post(
        "https://rancher.example.com/v3/clusters/local",
        params={"action": "generateKubeconfig"},
    ).mock(return_value=httpx.Response(200, json={"config": "apiVersion: v1"}))

    async with RancherManagementClient("work", build_config()) as client:
        result = await client.post_json(
            "/v3/clusters/local",
            params={"action": "generateKubeconfig"},
        )

    assert result == {"config": "apiVersion: v1"}
    assert route.called
    assert route.calls.last.request.headers["Authorization"].startswith("Bearer ")


@pytest.mark.asyncio
@respx.mock
async def test_patch_content_json_sends_custom_content_type() -> None:
    """Raw PATCH requests should preserve the caller-specified content type."""

    route = respx.patch(
        "https://rancher.example.com/v1/configmaps/default/demo",
        params={"fieldManager": "rancher-mcp"},
    ).mock(return_value=httpx.Response(200, json={"kind": "ConfigMap"}))

    async with RancherManagementClient("work", build_config()) as client:
        result = await client.patch_content_json(
            "/v1/configmaps/default/demo",
            content='{"kind":"ConfigMap"}',
            content_type="application/apply-patch+yaml",
            params={"fieldManager": "rancher-mcp"},
        )

    assert result == {"kind": "ConfigMap"}
    assert route.called
    assert route.calls.last.request.headers["Content-Type"] == "application/apply-patch+yaml"


@pytest.mark.asyncio
@respx.mock
async def test_delete_json_tolerates_empty_success_body() -> None:
    """DELETE requests should normalize empty 2xx responses into empty objects."""

    respx.delete("https://rancher.example.com/v3/projects/c-local:p-test").mock(
        return_value=httpx.Response(204)
    )

    async with RancherManagementClient("work", build_config()) as client:
        result = await client.delete_json("/v3/projects/c-local:p-test")

    assert result == {}


@pytest.mark.asyncio
@respx.mock
async def test_get_json_retries_transient_503_response() -> None:
    """JSON requests should retry transient Rancher HTTP failures before succeeding."""

    attempts = 0

    def responder(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"message": "temporarily unavailable"})
        return httpx.Response(200, json={"id": "server-version", "value": "v2.6.5"})

    respx.get("https://rancher.example.com/v3/settings/server-version").mock(side_effect=responder)

    async with RancherManagementClient("work", build_config()) as client:
        result = await client.get_json("/v3/settings/server-version")

    assert attempts == 2
    assert result == {"id": "server-version", "value": "v2.6.5"}


@pytest.mark.asyncio
@respx.mock
async def test_get_text_retries_transport_errors() -> None:
    """Text requests should retry transient transport failures before succeeding."""

    attempts = 0

    def responder(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadError("transient read error", request=request)
        return httpx.Response(200, text="ok")

    respx.get("https://rancher.example.com/healthz").mock(side_effect=responder)

    async with RancherManagementClient("work", build_config()) as client:
        result = await client.get_text("/healthz")

    assert attempts == 2
    assert result == "ok"
