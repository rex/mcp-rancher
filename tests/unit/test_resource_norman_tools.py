"""Generic Norman resource tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.resources import (
    rancher_norman_resource_action_invoke,
    rancher_norman_resource_get,
    rancher_norman_resource_link_follow,
    rancher_norman_resource_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for resource handler tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubNormanClient:
    """Deterministic Norman client for generic resource tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake Norman schema and resource payloads."""

        if path == "/v3/schemas/cluster":
            assert params is None
            return {
                "id": "cluster",
                "pluralName": "clusters",
                "links": {
                    "collection": "https://rancher.work.example.com/v3/clusters",
                    "self": "https://rancher.work.example.com/v3/schemas/cluster",
                },
            }
        if path == "/v3/clusters":
            assert params == {
                "limit": 1,
                "name": "local",
                "sort": "name",
                "reverse": True,
            }
            return {
                "actions": {"create": "https://rancher.work.example.com/v3/clusters"},
                "filters": {"name": {}, "state": {}},
                "links": {"self": "https://rancher.work.example.com/v3/clusters"},
                "pagination": {"limit": 1, "total": 1},
                "resourceType": "cluster",
                "sort": {"name": "asc"},
                "data": [
                    {
                        "id": "local",
                        "type": "cluster",
                        "name": "local",
                        "links": {"self": "https://rancher.work.example.com/v3/clusters/local"},
                        "actions": {
                            "generateKubeconfig": "https://rancher.work.example.com/v3/clusters/local?action=generateKubeconfig"
                        },
                    }
                ],
            }
        if path == "/v3/clusters/local":
            assert params is None
            return {
                "id": "local",
                "type": "cluster",
                "name": "local",
                "links": {
                    "self": "https://rancher.work.example.com/v3/clusters/local",
                    "nodes": "https://rancher.work.example.com/v3/clusters/local/nodes",
                },
                "actions": {
                    "generateKubeconfig": "https://rancher.work.example.com/v3/clusters/local?action=generateKubeconfig"
                },
            }
        if path == "/v3/clusters/local/nodes":
            assert params is None
            return {
                "resourceType": "node",
                "data": [
                    {
                        "id": "local:m-node",
                        "type": "node",
                        "name": "m-node",
                    }
                ],
            }
        raise AssertionError(f"unexpected Norman path: {path}")

    async def post_json(
        self,
        path: str,
        payload: object = None,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake action payloads."""

        assert params is None
        if path == "/v3/clusters/local?action=generateKubeconfig":
            assert payload == {}
            return {"config": "apiVersion: v1"}
        raise AssertionError(f"unexpected Norman POST path: {path}")


@pytest.mark.asyncio
async def test_rancher_norman_resource_list_normalizes_collection() -> None:
    """Norman generic list should resolve the collection link and normalize items."""

    result = await rancher_norman_resource_list(
        schema_id="cluster",
        limit=1,
        sort_by="name",
        reverse=True,
        filters_json='{"name": "local"}',
        instance="work",
        settings=build_settings(),
        client=StubNormanClient(),
    )

    assert result.plane == "norman"
    assert result.schema_id == "cluster"
    assert result.collection_path == "/v3/clusters"
    assert result.resource_count == 1
    assert result.collection_action_keys == ["create"]
    assert result.available_filter_keys == ["name", "state"]
    assert result.applied_query_params == {
        "limit": 1,
        "name": "local",
        "sort": "name",
        "reverse": True,
    }
    assert result.resources[0].id == "local"
    assert result.resources[0].resource_path == "/v3/clusters/local"


@pytest.mark.asyncio
async def test_rancher_norman_resource_get_normalizes_detail() -> None:
    """Norman generic get should preserve actions, links, and payload."""

    result = await rancher_norman_resource_get(
        schema_id="cluster",
        resource_id="local",
        instance="work",
        settings=build_settings(),
        client=StubNormanClient(),
    )

    assert result.plane == "norman"
    assert result.resource_id == "local"
    assert result.resource_path == "/v3/clusters/local"
    assert result.action_keys == ["generateKubeconfig"]


@pytest.mark.asyncio
async def test_rancher_norman_resource_action_invoke_returns_normalized_result() -> None:
    """Norman generic action invocation should follow the resource action map."""

    result = await rancher_norman_resource_action_invoke(
        schema_id="cluster",
        resource_id="local",
        action_name="generateKubeconfig",
        instance="work",
        settings=build_settings(),
        client=StubNormanClient(),
    )

    assert result.plane == "norman"
    assert result.resource_id == "local"
    assert result.action_name == "generateKubeconfig"
    assert result.action_path == "/v3/clusters/local?action=generateKubeconfig"
    assert result.payload == {"config": "apiVersion: v1"}


@pytest.mark.asyncio
async def test_rancher_norman_resource_link_follow_returns_normalized_result() -> None:
    """Norman generic link follow should GET the linked Rancher path."""

    result = await rancher_norman_resource_link_follow(
        schema_id="cluster",
        resource_id="local",
        link_name="nodes",
        instance="work",
        settings=build_settings(),
        client=StubNormanClient(),
    )

    assert result.plane == "norman"
    assert result.resource_id == "local"
    assert result.link_name == "nodes"
    assert result.link_path == "/v3/clusters/local/nodes"
    assert result.payload["resourceType"] == "node"
