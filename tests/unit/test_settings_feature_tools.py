"""Curated settings/features tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.settings_features import (
    rancher_feature_get,
    rancher_features_list,
    rancher_setting_get,
    rancher_settings_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated settings/features tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubManagementClient:
    """Deterministic management client for curated settings/features tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake settings and features payloads."""

        if path == "/v3/settings":
            assert params == {
                "limit": 2,
                "source": "default",
                "customized": False,
                "sort": "name",
                "reverse": True,
            }
            return {
                "data": [
                    {
                        "id": "agent-image",
                        "name": "agent-image",
                        "value": "rancher/rancher-agent:v2.6.5",
                        "default": "rancher/rancher-agent:v2.6-head",
                        "source": "default",
                        "customized": False,
                    },
                    {
                        "id": "auth-user-info-max-age-seconds",
                        "name": "auth-user-info-max-age-seconds",
                        "value": "3600",
                        "default": "3600",
                        "source": "default",
                        "customized": False,
                    },
                ]
            }
        if path == "/v3/settings/server-version":
            assert params is None
            return {
                "id": "server-version",
                "name": "server-version",
                "value": "v2.6.5",
                "default": "dev",
                "source": "env",
                "customized": False,
            }
        if path == "/v3/features":
            assert params == {
                "limit": 5,
                "state": "active",
                "value": True,
            }
            return {
                "data": [
                    {
                        "id": "fleet",
                        "name": "fleet",
                        "state": "active",
                        "value": True,
                        "transitioning": "no",
                        "transitioningMessage": "",
                        "status": {
                            "description": "Install Fleet when starting Rancher",
                            "dynamic": False,
                            "default": True,
                        },
                    }
                ]
            }
        if path == "/v3/features/fleet":
            assert params is None
            return {
                "id": "fleet",
                "name": "fleet",
                "state": "active",
                "value": True,
                "transitioning": "no",
                "transitioningMessage": "",
                "status": {
                    "description": "Install Fleet when starting Rancher",
                    "dynamic": False,
                    "default": True,
                },
            }
        raise AssertionError(f"unexpected management path: {path}")


@pytest.mark.asyncio
async def test_rancher_settings_list_returns_typed_summaries() -> None:
    """Curated settings list should expose typed settings summaries."""

    result = await rancher_settings_list(
        limit=2,
        source="default",
        customized=False,
        sort_by="name",
        reverse=True,
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.setting_count == 2
    assert result.applied_query_params == {
        "limit": 2,
        "source": "default",
        "customized": False,
        "sort": "name",
        "reverse": True,
    }
    assert result.settings[0].id == "agent-image"
    assert result.settings[0].value == "rancher/rancher-agent:v2.6.5"


@pytest.mark.asyncio
async def test_rancher_setting_get_returns_typed_detail() -> None:
    """Curated setting detail should preserve the typed value and raw payload."""

    result = await rancher_setting_get(
        setting_id="server-version",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "server-version"
    assert result.value == "v2.6.5"
    assert result.payload["source"] == "env"


@pytest.mark.asyncio
async def test_rancher_features_list_returns_typed_summaries() -> None:
    """Curated features list should expose typed feature summaries."""

    result = await rancher_features_list(
        limit=5,
        state="active",
        enabled=True,
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.feature_count == 1
    assert result.applied_query_params == {
        "limit": 5,
        "state": "active",
        "value": True,
    }
    assert result.features[0].id == "fleet"
    assert result.features[0].enabled is True
    assert result.features[0].description == "Install Fleet when starting Rancher"


@pytest.mark.asyncio
async def test_rancher_feature_get_returns_typed_detail() -> None:
    """Curated feature detail should preserve typed status fields and raw payload."""

    result = await rancher_feature_get(
        feature_id="fleet",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "fleet"
    assert result.enabled is True
    assert result.dynamic is False
    assert result.payload["state"] == "active"


@pytest.mark.asyncio
async def test_rancher_settings_list_handles_empty_collection() -> None:
    """Curated settings list should handle an empty Rancher collection cleanly."""

    class EmptySettingsClient:
        """Deterministic empty collection client for settings tests."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return an empty settings payload."""

            assert path == "/v3/settings"
            assert params is None
            return {"data": []}

    result = await rancher_settings_list(
        instance="work",
        settings=build_settings(),
        client=EmptySettingsClient(),
    )

    assert result.instance == "work"
    assert result.setting_count == 0
    assert result.applied_query_params == {}
    assert result.settings == []
