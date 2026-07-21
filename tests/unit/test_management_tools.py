"""Management discovery tool tests."""

import pytest

import rancher_mcp
from rancher_mcp.config import AppSettings
from rancher_mcp.tools.discovery import rancher_server_health, rancher_server_version


class StubManagementClient:
    """Minimal injected client for handler tests."""

    def __init__(self, *, health_text: str = "ok", version: str = "v2.6.5") -> None:
        self._health_text = health_text
        self._version = version

    async def get_text(self, path: str, params: object = None) -> str:
        """Return a deterministic text response."""

        assert path == "/healthz"
        assert params is None
        return self._health_text

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return a deterministic JSON response."""

        assert path == "/v3/settings/server-version"
        assert params is None
        return {"value": self._version}


def build_settings() -> AppSettings:
    """Create deterministic settings for handler tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


@pytest.mark.asyncio
async def test_rancher_server_health_returns_structured_response() -> None:
    """Health tool should report the instance and success state."""

    result = await rancher_server_health(
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(health_text="ok"),
    )

    assert result.instance == "work"
    assert result.healthy is True
    assert result.message == "ok"


@pytest.mark.asyncio
async def test_rancher_server_version_parses_setting_value() -> None:
    """Version tool should parse the server-version setting."""

    result = await rancher_server_version(
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(version="v2.6.5"),
    )

    assert result.instance == "work"
    assert result.rancher_version == "v2.6.5"
    # L-3d: the tool also reports rancher-mcp's OWN version (no venv inspection).
    assert result.mcp_server_version == rancher_mcp.__version__
    assert result.mcp_server_version
