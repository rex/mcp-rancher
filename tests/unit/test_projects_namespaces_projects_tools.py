"""Curated project tool tests (list/get)."""

from __future__ import annotations

import pytest
from _projects_namespaces_support import StubManagementClient, build_settings

from rancher_mcp.tools.projects_namespaces import rancher_project_get, rancher_projects_list


@pytest.mark.asyncio
async def test_rancher_projects_list_returns_typed_summaries() -> None:
    """Curated projects list should expose typed project summaries."""

    result = await rancher_projects_list(
        cluster_id="venue-local",
        state="active",
        limit=2,
        sort_by="name",
        reverse=True,
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.project_count == 1
    assert result.applied_query_params == {
        "clusterId": "venue-local",
        "state": "active",
        "limit": 2,
        "sort": "name",
        "reverse": True,
    }
    assert result.projects[0].id == "venue-local:p-kzmtj"
    assert result.projects[0].system_project is True
    assert result.projects[0].condition_types_true == [
        "BackingNamespaceCreated",
        "CreatorMadeOwner",
    ]


@pytest.mark.asyncio
async def test_rancher_project_get_returns_typed_detail() -> None:
    """Curated project detail should expose conditions and action/link keys."""

    result = await rancher_project_get(
        project_id="venue-local:p-kzmtj",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "venue-local:p-kzmtj"
    assert result.system_project is True
    assert result.action_keys == ["exportYaml"]
    assert "pods" in result.link_keys
    assert result.conditions[0].type == "BackingNamespaceCreated"


@pytest.mark.asyncio
async def test_rancher_projects_list_handles_empty_collection() -> None:
    """Curated project list should handle an empty Norman collection cleanly."""

    class EmptyProjectClient:
        """Return an empty project collection."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic empty collection."""

            assert path == "/v3/projects"
            assert params is None
            return {"data": []}

    result = await rancher_projects_list(
        instance="work",
        settings=build_settings(),
        client=EmptyProjectClient(),
    )

    assert result.project_count == 0
    assert result.applied_query_params == {}
    assert result.projects == []
