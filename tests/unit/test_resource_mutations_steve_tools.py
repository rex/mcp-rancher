"""Generic Steve resource mutation tool tests."""

from __future__ import annotations

import json

import pytest
from _resource_mutations_support import build_settings

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.tools.resource_mutations import (
    rancher_steve_resource_apply,
    rancher_steve_resource_create,
    rancher_steve_resource_delete,
    rancher_steve_resource_patch,
)


class StubSteveDiscoveryClient:
    """Deterministic Steve discovery client for generic mutation tools."""

    async def get_text(self, path: str, params: object = None) -> str:
        """The mutation tests do not use text endpoints."""

        raise AssertionError(f"unexpected Steve GET text path: {path} params={params}")

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake Steve schema and current configmap payloads."""

        if path == "/schemas/configmap":
            assert params is None
            return {
                "id": "configmap",
                "pluralName": "configmaps",
                "collectionMethods": ["GET", "POST"],
                "resourceMethods": ["GET", "DELETE", "PUT", "PATCH"],
                "links": {
                    "collection": (
                        "https://rancher.work.example.com/k8s/clusters/venue-local/v1/configmaps"
                    ),
                    "self": (
                        "https://rancher.work.example.com/k8s/clusters/venue-local/v1/schemas/configmap"
                    ),
                },
                "attributes": {
                    "namespaced": True,
                    "group": "",
                    "version": "v1",
                    "resource": "configmaps",
                    "verbs": ["create", "delete", "patch", "update", "get", "list"],
                },
                "resourceFields": {
                    "apiVersion": {"create": True, "update": True},
                    "kind": {"create": True, "update": True},
                    "metadata": {"create": True, "update": True},
                    "data": {"create": True, "update": True},
                },
            }
        if path == "/configmaps/default/demo-config":
            assert params is None
            return {
                "id": "default/demo-config",
                "type": "configmap",
                "metadata": {
                    "name": "demo-config",
                    "namespace": "default",
                },
                "data": {"key": "before"},
                "links": {
                    "self": (
                        "https://rancher.work.example.com/k8s/clusters/venue-local/v1/"
                        "configmaps/default/demo-config"
                    )
                },
            }
        raise AssertionError(f"unexpected Steve path: {path}")


class StubSteveManagementClient:
    """Deterministic management client for Steve mutation requests."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Steve mutation tests do not use management-plane GET requests."""

        raise AssertionError(f"unexpected Steve management GET path: {path} params={params}")

    async def get_text(self, path: str, params: object = None) -> str:
        """Steve mutation tests do not use management-plane text requests."""

        raise AssertionError(f"unexpected Steve management GET text path: {path} params={params}")

    async def post_json(
        self,
        path: str,
        payload: object = None,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake Steve create responses."""

        assert path == "/k8s/clusters/venue-local/api/v1/namespaces/default/configmaps"
        assert params is None
        assert payload == {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "demo-config", "namespace": "default"},
            "data": {"key": "created"},
        }
        return {
            "id": "default/demo-config",
            "type": "configmap",
            "metadata": {"name": "demo-config", "namespace": "default"},
            "data": {"key": "created"},
        }

    async def put_json(
        self,
        path: str,
        payload: object = None,
        params: object = None,
    ) -> dict[str, object]:
        """Steve mutation tests do not use management-plane PUT requests."""

        raise AssertionError(f"unexpected Steve management PUT path: {path} payload={payload}")

    async def patch_json(
        self,
        path: str,
        payload: object = None,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake Steve merge-patch responses."""

        assert path == "/k8s/clusters/venue-local/api/v1/namespaces/default/configmaps/demo-config"
        assert params == {"dryRun": "All"}
        assert payload == {"data": {"key": "patched"}}
        return {
            "id": "default/demo-config",
            "type": "configmap",
            "metadata": {"name": "demo-config", "namespace": "default"},
            "data": {"key": "patched"},
        }

    async def patch_content_json(
        self,
        path: str,
        content: str,
        *,
        content_type: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake Steve server-side-apply responses."""

        assert path == "/k8s/clusters/venue-local/api/v1/namespaces/default/configmaps/demo-config"
        assert content_type == "application/apply-patch+yaml"
        assert params == {"fieldManager": "rancher-mcp", "force": True}
        assert json.loads(content) == {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "demo-config", "namespace": "default"},
            "data": {"key": "applied"},
        }
        return {
            "id": "default/demo-config",
            "type": "configmap",
            "metadata": {"name": "demo-config", "namespace": "default"},
            "data": {"key": "applied"},
        }

    async def delete_json(
        self,
        path: str,
        payload: object = None,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake Steve delete responses."""

        assert path == "/k8s/clusters/venue-local/api/v1/namespaces/default/configmaps/demo-config"
        assert payload == {"gracePeriodSeconds": 0}
        assert params is None
        return {}


@pytest.mark.asyncio
async def test_rancher_steve_resource_create_normalizes_created_resource() -> None:
    """Steve generic create should POST to the namespace-scoped collection path."""

    result = await rancher_steve_resource_create(
        schema_id="configmap",
        cluster_id="venue-local",
        namespace="default",
        payload_json=(
            '{"apiVersion": "v1", "kind": "ConfigMap", '
            '"metadata": {"name": "demo-config", "namespace": "default"}, '
            '"data": {"key": "created"}}'
        ),
        instance="work",
        settings=build_settings(),
        steve_client=StubSteveDiscoveryClient(),
        management_client=StubSteveManagementClient(),
    )

    assert result.plane == "steve"
    assert result.operation == "create"
    assert result.request_path == "/k8s/clusters/venue-local/api/v1/namespaces/default/configmaps"
    assert result.resource_id == "default/demo-config"


@pytest.mark.asyncio
async def test_rancher_steve_resource_apply_uses_server_side_apply_contract() -> None:
    """Steve generic apply should use the apply patch content type and query params."""

    result = await rancher_steve_resource_apply(
        schema_id="configmap",
        resource_id="demo-config",
        cluster_id="venue-local",
        namespace="default",
        payload_json=(
            '{"apiVersion": "v1", "kind": "ConfigMap", '
            '"metadata": {"name": "demo-config", "namespace": "default"}, '
            '"data": {"key": "applied"}}'
        ),
        field_manager="rancher-mcp",
        force=True,
        instance="work",
        settings=build_settings(),
        steve_client=StubSteveDiscoveryClient(),
        management_client=StubSteveManagementClient(),
    )

    assert result.operation == "apply"
    assert result.request_method == "PATCH"
    assert result.payload["data"] == {"key": "applied"}


@pytest.mark.asyncio
async def test_rancher_steve_resource_patch_uses_merge_patch() -> None:
    """Steve generic patch should issue a JSON merge patch against the resource path."""

    result = await rancher_steve_resource_patch(
        schema_id="configmap",
        resource_id="demo-config",
        cluster_id="venue-local",
        namespace="default",
        payload_json='{"data": {"key": "patched"}}',
        params_json='{"dryRun": "All"}',
        instance="work",
        settings=build_settings(),
        steve_client=StubSteveDiscoveryClient(),
        management_client=StubSteveManagementClient(),
    )

    assert result.operation == "patch"
    assert result.payload["data"] == {"key": "patched"}


@pytest.mark.asyncio
async def test_rancher_steve_resource_delete_requires_confirmation_phrase() -> None:
    """Steve generic delete should enforce the shared destructive confirmation."""

    result = await rancher_steve_resource_delete(
        schema_id="configmap",
        resource_id="demo-config",
        confirmation="delete steve configmap demo-config",
        cluster_id="venue-local",
        namespace="default",
        payload_json='{"gracePeriodSeconds": 0}',
        instance="work",
        settings=build_settings(),
        steve_client=StubSteveDiscoveryClient(),
        management_client=StubSteveManagementClient(),
    )

    assert result.operation == "delete"
    assert result.resource_id == "default/demo-config"
    assert (
        result.resource_path
        == "/k8s/clusters/venue-local/api/v1/namespaces/default/configmaps/demo-config"
    )


@pytest.mark.asyncio
async def test_generic_resource_mutations_reject_read_only_instances() -> None:
    """All generic mutations should reject read-only instance configurations."""

    with pytest.raises(RancherCapabilityError, match="configured read-only for mutations"):
        await rancher_steve_resource_patch(
            schema_id="configmap",
            resource_id="demo-config",
            cluster_id="venue-local",
            namespace="default",
            payload_json='{"data": {"key": "patched"}}',
            instance="work",
            settings=build_settings(read_only=True),
            steve_client=StubSteveDiscoveryClient(),
            management_client=StubSteveManagementClient(),
        )
