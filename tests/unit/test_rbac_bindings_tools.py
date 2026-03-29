"""Curated RBAC binding tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.rbac import (
    rancher_cluster_role_template_binding_get,
    rancher_cluster_role_template_bindings_list,
    rancher_global_role_binding_get,
    rancher_global_role_bindings_list,
    rancher_project_role_template_binding_get,
    rancher_project_role_template_bindings_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated RBAC binding tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubManagementClient:
    """Deterministic management client for curated RBAC binding tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake binding payloads."""

        if path == "/v3/globalrolebindings":
            assert params == {
                "limit": 2,
                "globalRoleId": "admin",
                "userId": "user-admin",
                "sort": "name",
            }
            return {
                "data": [
                    {
                        "id": "globalrolebinding-admin",
                        "name": "globalrolebinding-admin",
                        "globalRoleId": "admin",
                        "userId": "user-admin",
                    }
                ]
            }
        if path == "/v3/globalrolebindings/globalrolebinding-admin":
            assert params is None
            return {
                "id": "globalrolebinding-admin",
                "name": "globalrolebinding-admin",
                "globalRoleId": "admin",
                "userId": "user-admin",
                "links": {
                    "self": "https://rancher.work.example.com/v3/globalrolebindings/globalrolebinding-admin",
                },
            }
        if path == "/v3/clusterroletemplatebindings":
            assert params == {
                "limit": 2,
                "clusterId": "local",
                "roleTemplateId": "cluster-owner",
            }
            return {"data": []}
        if path == "/v3/clusterroletemplatebindings/crtb-admin":
            assert params is None
            return {
                "id": "crtb-admin",
                "name": "crtb-admin",
                "clusterId": "local",
                "roleTemplateId": "cluster-owner",
                "userPrincipalId": "local://user-admin",
                "links": {
                    "self": "https://rancher.work.example.com/v3/clusterroletemplatebindings/crtb-admin",
                },
            }
        if path == "/v3/projectroletemplatebindings":
            assert params == {
                "limit": 2,
                "projectId": "local:p-abcde",
                "roleTemplateId": "project-owner",
            }
            return {"data": []}
        if path == "/v3/projectroletemplatebindings/prtb-admin":
            assert params is None
            return {
                "id": "prtb-admin",
                "name": "prtb-admin",
                "projectId": "local:p-abcde",
                "roleTemplateId": "project-owner",
                "serviceAccount": "cattle-system:default",
                "links": {
                    "self": "https://rancher.work.example.com/v3/projectroletemplatebindings/prtb-admin",
                },
            }
        raise AssertionError(f"unexpected management path: {path}")


@pytest.mark.asyncio
async def test_rancher_global_role_bindings_list_returns_typed_summaries() -> None:
    """Curated global-role-binding list should expose typed summaries."""

    result = await rancher_global_role_bindings_list(
        limit=2,
        global_role_id="admin",
        user_id="user-admin",
        sort_by="name",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.global_role_binding_count == 1
    assert result.global_role_bindings[0].global_role_id == "admin"


@pytest.mark.asyncio
async def test_rancher_global_role_binding_get_returns_typed_detail() -> None:
    """Curated global-role-binding detail should expose the derived subject."""

    result = await rancher_global_role_binding_get(
        global_role_binding_id="globalrolebinding-admin",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "globalrolebinding-admin"
    assert result.subject_kind == "user"
    assert result.subject_id == "user-admin"
    assert result.link_keys == ["self"]


@pytest.mark.asyncio
async def test_rancher_cluster_role_template_bindings_list_handles_empty_collection() -> None:
    """Curated cluster binding list should handle an empty collection cleanly."""

    result = await rancher_cluster_role_template_bindings_list(
        limit=2,
        cluster_id="local",
        role_template_id="cluster-owner",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.cluster_role_template_binding_count == 0
    assert result.cluster_role_template_bindings == []


@pytest.mark.asyncio
async def test_rancher_cluster_role_template_binding_get_returns_typed_detail() -> None:
    """Curated cluster binding detail should expose the derived subject."""

    result = await rancher_cluster_role_template_binding_get(
        cluster_role_template_binding_id="crtb-admin",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "crtb-admin"
    assert result.subject_kind == "user_principal"
    assert result.subject_id == "local://user-admin"
    assert result.link_keys == ["self"]


@pytest.mark.asyncio
async def test_rancher_project_role_template_bindings_list_handles_empty_collection() -> None:
    """Curated project binding list should handle an empty collection cleanly."""

    result = await rancher_project_role_template_bindings_list(
        limit=2,
        project_id="local:p-abcde",
        role_template_id="project-owner",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.project_role_template_binding_count == 0
    assert result.project_role_template_bindings == []


@pytest.mark.asyncio
async def test_rancher_project_role_template_binding_get_returns_typed_detail() -> None:
    """Curated project binding detail should expose the derived subject."""

    result = await rancher_project_role_template_binding_get(
        project_role_template_binding_id="prtb-admin",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "prtb-admin"
    assert result.subject_kind == "service_account"
    assert result.subject_id == "cattle-system:default"
    assert result.link_keys == ["self"]
