"""Curated Fleet workspace tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.fleet_registration import (
    rancher_fleet_workspace_get,
    rancher_fleet_workspaces_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated Fleet workspace tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubManagementClient:
    """Deterministic management client for curated Fleet workspace tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake Fleet workspace payloads."""

        if path == "/v3/fleetworkspaces":
            assert params == {
                "limit": 2,
                "name": "fleet-default",
                "sort": "name",
            }
            return {
                "data": [
                    {
                        "id": "fleet-default",
                        "name": "fleet-default",
                    }
                ]
            }
        if path == "/v3/fleetworkspaces/fleet-default":
            assert params is None
            return {
                "id": "fleet-default",
                "name": "fleet-default",
                "status": {"readyBundles": 1},
                "links": {
                    "self": "https://rancher.work.example.com/v3/fleetworkspaces/fleet-default",
                    "update": "https://rancher.work.example.com/v3/fleetworkspaces/fleet-default",
                },
                "actions": {
                    "noop": "https://rancher.work.example.com/v3/fleetworkspaces/fleet-default?action=noop",
                },
            }
        raise AssertionError(f"unexpected management path: {path}")


@pytest.mark.asyncio
async def test_rancher_fleet_workspaces_list_returns_typed_summaries() -> None:
    """Curated Fleet workspace list should expose typed summaries."""

    result = await rancher_fleet_workspaces_list(
        limit=2,
        name="fleet-default",
        sort_by="name",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.fleet_workspace_count == 1
    assert result.fleet_workspaces[0].id == "fleet-default"


@pytest.mark.asyncio
async def test_rancher_fleet_workspace_get_returns_typed_detail() -> None:
    """Curated Fleet workspace detail should expose status and keys."""

    result = await rancher_fleet_workspace_get(
        fleet_workspace_id="fleet-default",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "fleet-default"
    assert result.status == {"readyBundles": 1}
    assert result.status_keys == ["readyBundles"]
    assert result.action_keys == ["noop"]
    assert result.link_keys == ["self", "update"]
