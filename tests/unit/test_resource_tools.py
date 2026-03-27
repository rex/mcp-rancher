"""Generic resource tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.resources import (
    rancher_norman_resource_get,
    rancher_norman_resource_list,
    rancher_steve_resource_get,
    rancher_steve_resource_list,
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
            assert params == {"limit": 1, "name": "local"}
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
                "links": {"self": "https://rancher.work.example.com/v3/clusters/local"},
                "actions": {
                    "generateKubeconfig": "https://rancher.work.example.com/v3/clusters/local?action=generateKubeconfig"
                },
            }
        raise AssertionError(f"unexpected Norman path: {path}")


class StubSteveClient:
    """Deterministic Steve client for generic resource tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake Steve schema and resource payloads."""

        if path == "/schemas/pod":
            assert params is None
            return {
                "id": "pod",
                "pluralName": "pods",
                "links": {
                    "collection": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/pods",
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/schemas/pod",
                },
                "attributes": {
                    "namespaced": True,
                },
            }
        if path == "/pods/cattle-system":
            assert params == {"limit": 1}
            return {
                "links": {
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/pods/cattle-system"
                },
                "pagination": {"continue": "cursor-123"},
                "resourceType": "pod",
                "data": [
                    {
                        "id": "cattle-system/test-pod",
                        "type": "pod",
                        "metadata": {
                            "name": "test-pod",
                            "namespace": "cattle-system",
                        },
                        "links": {
                            "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/pods/cattle-system/test-pod"
                        },
                    }
                ],
            }
        if path == "/pods/cattle-system/test-pod":
            assert params is None
            return {
                "id": "cattle-system/test-pod",
                "type": "pod",
                "metadata": {
                    "name": "test-pod",
                    "namespace": "cattle-system",
                },
                "links": {
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/pods/cattle-system/test-pod"
                },
            }
        raise AssertionError(f"unexpected Steve path: {path}")


@pytest.mark.asyncio
async def test_rancher_norman_resource_list_normalizes_collection() -> None:
    """Norman generic list should resolve the collection link and normalize items."""

    result = await rancher_norman_resource_list(
        schema_id="cluster",
        params_json='{"limit": 1, "name": "local"}',
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
async def test_rancher_steve_resource_list_uses_namespace_scope_when_requested() -> None:
    """Steve generic list should build namespace-scoped collection paths."""

    result = await rancher_steve_resource_list(
        schema_id="pod",
        cluster_id="venue-local",
        namespace="cattle-system",
        params_json='{"limit": 1}',
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.plane == "steve"
    assert result.cluster_id == "venue-local"
    assert result.collection_path == "/pods/cattle-system"
    assert result.pagination is not None
    assert result.pagination.continue_token is not None
    assert result.pagination.continue_token.startswith("cursor-")
    assert result.resources[0].namespace == "cattle-system"
    assert result.resources[0].resource_path == "/pods/cattle-system/test-pod"


@pytest.mark.asyncio
async def test_rancher_steve_resource_get_uses_namespace_scope_for_name_only_ids() -> None:
    """Steve generic get should scope namespaced resources by namespace when needed."""

    result = await rancher_steve_resource_get(
        schema_id="pod",
        resource_id="test-pod",
        cluster_id="venue-local",
        namespace="cattle-system",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.plane == "steve"
    assert result.resource_id == "cattle-system/test-pod"
    assert result.namespace == "cattle-system"
    assert result.resource_path == "/pods/cattle-system/test-pod"
