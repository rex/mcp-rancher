"""Curated RBAC role tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.rbac import (
    rancher_global_role_get,
    rancher_global_roles_list,
    rancher_role_template_get,
    rancher_role_templates_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated RBAC role tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubManagementClient:
    """Deterministic management client for curated RBAC role tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake global-role and role-template payloads."""

        if path == "/v3/globalroles":
            assert params == {
                "limit": 2,
                "builtin": True,
                "name": "Admin",
                "newUserDefault": False,
                "sort": "name",
            }
            return {
                "data": [
                    {
                        "id": "admin",
                        "name": "Admin",
                        "description": "Full access",
                        "builtin": True,
                        "newUserDefault": False,
                    }
                ]
            }
        if path == "/v3/globalroles/admin":
            assert params is None
            return {
                "id": "admin",
                "name": "Admin",
                "description": "Full access",
                "builtin": True,
                "newUserDefault": False,
                "rules": [
                    {
                        "apiGroups": ["*"],
                        "resources": ["*"],
                        "verbs": ["*"],
                        "nonResourceURLs": ["/healthz"],
                    }
                ],
                "actions": {
                    "noop": "https://rancher.work.example.com/v3/globalroles/admin?action=noop"
                },
                "links": {
                    "self": "https://rancher.work.example.com/v3/globalroles/admin",
                    "update": "https://rancher.work.example.com/v3/globalroles/admin",
                },
            }
        if path == "/v3/roletemplates":
            assert params == {
                "limit": 2,
                "builtin": True,
                "context": "project",
                "administrative": False,
                "projectCreatorDefault": False,
                "hidden": False,
                "locked": True,
                "sort": "name",
            }
            return {
                "data": [
                    {
                        "id": "admin",
                        "name": "Kubernetes admin",
                        "builtin": True,
                        "context": "project",
                        "administrative": False,
                        "projectCreatorDefault": False,
                        "hidden": False,
                        "locked": True,
                        "roleTemplateIds": ["view"],
                    }
                ]
            }
        if path == "/v3/roletemplates/admin":
            assert params is None
            return {
                "id": "admin",
                "name": "Kubernetes admin",
                "builtin": True,
                "context": "project",
                "administrative": False,
                "clusterCreatorDefault": False,
                "projectCreatorDefault": False,
                "external": False,
                "hidden": False,
                "locked": True,
                "roleTemplateIds": ["view"],
                "rules": [],
                "links": {
                    "self": "https://rancher.work.example.com/v3/roletemplates/admin",
                    "update": "https://rancher.work.example.com/v3/roletemplates/admin",
                },
            }
        raise AssertionError(f"unexpected management path: {path}")


@pytest.mark.asyncio
async def test_rancher_global_roles_list_returns_typed_summaries() -> None:
    """Curated global-role list should expose typed summaries."""

    result = await rancher_global_roles_list(
        limit=2,
        builtin=True,
        name="Admin",
        new_user_default=False,
        sort_by="name",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.global_role_count == 1
    assert result.global_roles[0].new_user_default is False


@pytest.mark.asyncio
async def test_rancher_global_role_get_returns_typed_detail() -> None:
    """Curated global-role detail should expose rules and keys."""

    result = await rancher_global_role_get(
        global_role_id="admin",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "admin"
    assert result.rule_count == 1
    assert result.rules[0].api_groups == ["*"]
    assert result.rules[0].non_resource_urls == ["/healthz"]
    assert result.action_keys == ["noop"]
    assert result.link_keys == ["self", "update"]


@pytest.mark.asyncio
async def test_rancher_role_templates_list_returns_typed_summaries() -> None:
    """Curated role-template list should expose typed summaries."""

    result = await rancher_role_templates_list(
        limit=2,
        builtin=True,
        context="project",
        administrative=False,
        project_creator_default=False,
        hidden=False,
        locked=True,
        sort_by="name",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.role_template_count == 1
    assert result.role_templates[0].context == "project"
    assert result.role_templates[0].inherited_role_template_ids == ["view"]


@pytest.mark.asyncio
async def test_rancher_role_template_get_returns_typed_detail() -> None:
    """Curated role-template detail should expose inherited-role counts and keys."""

    result = await rancher_role_template_get(
        role_template_id="admin",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "admin"
    assert result.inherited_role_template_count == 1
    assert result.rule_count == 0
    assert result.link_keys == ["self", "update"]
