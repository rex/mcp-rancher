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
