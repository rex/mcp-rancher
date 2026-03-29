"""Curated auth and identity tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.auth_identity import (
    rancher_auth_config_get,
    rancher_auth_configs_list,
    rancher_group_get,
    rancher_groups_list,
    rancher_user_get,
    rancher_users_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated auth and identity tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubManagementClient:
    """Deterministic management client for auth and identity tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake user, group, and auth-config payloads."""

        if path == "/v3/users":
            assert params == {
                "limit": 2,
                "state": "active",
                "enabled": True,
                "me": True,
                "sort": "name",
                "reverse": True,
            }
            return {
                "data": [
                    {
                        "id": "user-admin",
                        "name": "Default Admin",
                        "username": "admin",
                        "enabled": True,
                        "me": True,
                        "mustChangePassword": False,
                        "state": "active",
                        "principalIds": ["local://user-admin"],
                    }
                ]
            }
        if path == "/v3/users/user-admin":
            assert params is None
            return {
                "id": "user-admin",
                "name": "Default Admin",
                "username": "admin",
                "enabled": True,
                "me": True,
                "mustChangePassword": False,
                "state": "active",
                "principalIds": ["local://user-admin"],
                "conditions": [{"type": "Active", "status": "True"}],
                "actions": {
                    "setpassword": "https://rancher.work.example.com/v3/users/user-admin?action=setpassword"
                },
                "links": {
                    "self": "https://rancher.work.example.com/v3/users/user-admin",
                    "tokens": "https://rancher.work.example.com/v3/users/user-admin/tokens",
                },
            }
        if path == "/v3/groups":
            assert params == {
                "limit": 2,
                "name": "local-admins",
                "sort": "name",
            }
            return {
                "data": [
                    {
                        "id": "local://local-admins",
                        "name": "local-admins",
                        "principalType": "group",
                    }
                ]
            }
        if path == "/v3/groups/local://local-admins":
            assert params is None
            return {
                "id": "local://local-admins",
                "name": "local-admins",
                "principalType": "group",
                "created": "2026-03-27T18:13:53Z",
                "createdTS": 1774635233000,
                "creatorId": None,
                "links": {
                    "self": "https://rancher.work.example.com/v3/groups/local://local-admins",
                },
            }
        if path == "/v3/authconfigs":
            assert params == {
                "limit": 2,
                "enabled": True,
                "type": "localConfig",
                "sort": "name",
            }
            return {
                "data": [
                    {
                        "id": "local",
                        "name": "local",
                        "type": "localConfig",
                        "enabled": True,
                    }
                ]
            }
        if path == "/v3/authconfigs/local":
            assert params is None
            return {
                "id": "local",
                "name": "local",
                "type": "localConfig",
                "enabled": True,
                "created": "2026-03-27T18:13:53Z",
                "createdTS": 1774635233000,
                "creatorId": None,
                "links": {
                    "self": "https://rancher.work.example.com/v3/authconfigs/local",
                },
            }
        raise AssertionError(f"unexpected management path: {path}")


@pytest.mark.asyncio
async def test_rancher_users_list_returns_typed_summaries() -> None:
    """Curated users list should expose typed user summaries."""

    result = await rancher_users_list(
        limit=2,
        state="active",
        enabled=True,
        me=True,
        sort_by="name",
        reverse=True,
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.user_count == 1
    assert result.users[0].username == "admin"
    assert result.users[0].principal_ids == ["local://user-admin"]


@pytest.mark.asyncio
async def test_rancher_user_get_returns_typed_detail() -> None:
    """Curated user detail should expose condition, action, and link detail."""

    result = await rancher_user_get(
        user_id="user-admin",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "user-admin"
    assert result.condition_types_true == ["Active"]
    assert result.action_keys == ["setpassword"]
    assert "tokens" in result.link_keys


@pytest.mark.asyncio
async def test_rancher_groups_list_returns_typed_summaries() -> None:
    """Curated groups list should expose typed group summaries."""

    result = await rancher_groups_list(
        limit=2,
        name="local-admins",
        sort_by="name",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.group_count == 1
    assert result.groups[0].principal_type == "group"


@pytest.mark.asyncio
async def test_rancher_group_get_returns_typed_detail() -> None:
    """Curated group detail should expose created metadata and link keys."""

    result = await rancher_group_get(
        group_id="local://local-admins",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "local://local-admins"
    assert result.created_ts == 1774635233000
    assert result.link_keys == ["self"]


@pytest.mark.asyncio
async def test_rancher_auth_configs_list_returns_typed_summaries() -> None:
    """Curated auth-config list should expose typed provider summaries."""

    result = await rancher_auth_configs_list(
        limit=2,
        enabled=True,
        provider_type="localConfig",
        sort_by="name",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.auth_config_count == 1
    assert result.auth_configs[0].provider_type == "localConfig"


@pytest.mark.asyncio
async def test_rancher_auth_config_get_returns_typed_detail() -> None:
    """Curated auth-config detail should expose links and payload shape."""

    result = await rancher_auth_config_get(
        auth_config_id="local",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "local"
    assert result.enabled is True
    assert result.link_keys == ["self"]


@pytest.mark.asyncio
async def test_rancher_groups_list_handles_empty_collection() -> None:
    """Curated groups list should handle an empty collection cleanly."""

    class EmptyGroupClient:
        """Return an empty groups collection."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic empty groups payload."""

            assert path == "/v3/groups"
            assert params is None
            return {"data": []}

    result = await rancher_groups_list(
        instance="work",
        settings=build_settings(),
        client=EmptyGroupClient(),
    )

    assert result.group_count == 0
    assert result.applied_query_params == {}
    assert result.groups == []
