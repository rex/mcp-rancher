"""Generic Steve resource tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.resources import (
    rancher_steve_resource_action_invoke,
    rancher_steve_resource_get,
    rancher_steve_resource_link_follow,
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
            assert params == {
                "limit": 1,
                "labelSelector": "app=cattle-cluster-agent",
                "fieldSelector": "metadata.name=test-pod",
            }
            return {
                "links": {
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/pods/cattle-system"
                },
                "pagination": {
                    "next": (
                        "https://rancher.work.example.com/k8s/clusters/venue-local/v1/pods/"
                        "cattle-system?continue=cursor-123&limit=1"
                    )
                },
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
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/pods/cattle-system/test-pod",
                    "view": "https://rancher.work.example.com/k8s/clusters/venue-local/api/v1/namespaces/cattle-system/pods/test-pod",
                },
                "actions": {
                    "restart": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/pods/cattle-system/test-pod?action=restart"
                },
            }
        raise AssertionError(f"unexpected Steve path: {path}")


class StubSteveManagementClient:
    """Deterministic Rancher management client for Steve action/link follow-up calls."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake management-plane follow-up payloads."""

        assert params is None
        if path == "/k8s/clusters/venue-local/api/v1/namespaces/cattle-system/pods/test-pod":
            return {
                "kind": "Pod",
                "metadata": {
                    "name": "test-pod",
                    "namespace": "cattle-system",
                },
            }
        raise AssertionError(f"unexpected Steve management GET path: {path}")

    async def post_json(
        self,
        path: str,
        payload: object = None,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake management-plane action responses."""

        assert params is None
        if path == "/k8s/clusters/venue-local/v1/pods/cattle-system/test-pod?action=restart":
            assert payload == {"gracePeriodSeconds": 0}
            return {"status": "queued"}
        raise AssertionError(f"unexpected Steve management POST path: {path}")


@pytest.mark.asyncio
async def test_rancher_steve_resource_list_uses_namespace_scope_when_requested() -> None:
    """Steve generic list should build namespace-scoped collection paths."""

    result = await rancher_steve_resource_list(
        schema_id="pod",
        cluster_id="venue-local",
        namespace="cattle-system",
        limit=1,
        label_selector="app=cattle-cluster-agent",
        field_selector="metadata.name=test-pod",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.plane == "steve"
    assert result.cluster_id == "venue-local"
    assert result.collection_path == "/pods/cattle-system"
    assert result.applied_query_params == {
        "limit": 1,
        "labelSelector": "app=cattle-cluster-agent",
        "fieldSelector": "metadata.name=test-pod",
    }
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


@pytest.mark.asyncio
async def test_rancher_steve_resource_action_invoke_uses_management_plane_for_post() -> None:
    """Steve generic actions should POST through the management client using Rancher paths."""

    result = await rancher_steve_resource_action_invoke(
        schema_id="pod",
        resource_id="test-pod",
        action_name="restart",
        cluster_id="venue-local",
        namespace="cattle-system",
        payload_json='{"gracePeriodSeconds": 0}',
        instance="work",
        settings=build_settings(),
        steve_client=StubSteveClient(),
        management_client=StubSteveManagementClient(),
    )

    assert result.plane == "steve"
    assert result.resource_id == "cattle-system/test-pod"
    assert result.namespace == "cattle-system"
    assert (
        result.action_path
        == "/k8s/clusters/venue-local/v1/pods/cattle-system/test-pod?action=restart"
    )
    assert result.payload == {"status": "queued"}


@pytest.mark.asyncio
async def test_rancher_steve_resource_link_follow_uses_management_plane_for_follow_up() -> None:
    """Steve generic links should follow the Rancher-exposed target path verbatim."""

    result = await rancher_steve_resource_link_follow(
        schema_id="pod",
        resource_id="test-pod",
        link_name="view",
        cluster_id="venue-local",
        namespace="cattle-system",
        instance="work",
        settings=build_settings(),
        steve_client=StubSteveClient(),
        management_client=StubSteveManagementClient(),
    )

    assert result.plane == "steve"
    assert result.resource_id == "cattle-system/test-pod"
    assert result.link_name == "view"
    assert (
        result.link_path
        == "/k8s/clusters/venue-local/api/v1/namespaces/cattle-system/pods/test-pod"
    )
    assert result.payload["kind"] == "Pod"
