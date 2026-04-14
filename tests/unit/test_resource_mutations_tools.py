"""Generic resource mutation tool tests."""

from __future__ import annotations

import json

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.tools.resource_mutations import (
    rancher_norman_resource_apply,
    rancher_norman_resource_create,
    rancher_norman_resource_delete,
    rancher_norman_resource_patch,
    rancher_steve_resource_apply,
    rancher_steve_resource_create,
    rancher_steve_resource_delete,
    rancher_steve_resource_patch,
)


def build_settings(*, read_only: bool = False) -> AppSettings:
    """Create deterministic settings for mutation handler tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=json.dumps(
            {
                "work": {
                    "url": "https://rancher.work.example.com",
                    "token": "token-work:secret",
                    "verify_ssl": True,
                    "read_only": read_only,
                }
            }
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubNormanMutationClient:
    """Deterministic Norman client for generic mutation tools."""

    async def get_text(self, path: str, params: object = None) -> str:
        """The mutation tests do not use text endpoints."""

        raise AssertionError(f"unexpected Norman GET text path: {path} params={params}")

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake Norman schema and current project payloads."""

        if path == "/v3/schemas/project":
            assert params is None
            return {
                "id": "project",
                "pluralName": "projects",
                "collectionMethods": ["GET", "POST"],
                "resourceMethods": ["GET", "PUT", "DELETE"],
                "links": {
                    "collection": "https://rancher.work.example.com/v3/projects",
                    "self": "https://rancher.work.example.com/v3/schemas/project",
                },
                "resourceFields": {
                    "name": {"create": True, "update": True},
                    "clusterId": {"create": True, "update": False},
                    "description": {"create": True, "update": True},
                },
            }
        if path == "/v3/projects/c-local%3Ap-demo":
            assert params is None
            return {
                "id": "c-local:p-demo",
                "type": "project",
                "name": "phase3-demo",
                "clusterId": "local",
                "description": "before",
                "links": {"self": "https://rancher.work.example.com/v3/projects/c-local:p-demo"},
            }
        raise AssertionError(f"unexpected Norman path: {path}")

    async def post_json(
        self,
        path: str,
        payload: object = None,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake Norman create responses."""

        assert params == {"validateOnly": False}
        if path == "/v3/projects":
            assert payload == {
                "clusterId": "local",
                "name": "phase3-demo",
                "description": "created",
            }
            return {
                "id": "c-local:p-demo",
                "type": "project",
                "name": "phase3-demo",
                "description": "created",
                "links": {"self": "https://rancher.work.example.com/v3/projects/c-local:p-demo"},
            }
        raise AssertionError(f"unexpected Norman POST path: {path}")

    async def put_json(
        self,
        path: str,
        payload: object = None,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake Norman PUT responses for apply and patch."""

        assert path == "/v3/projects/c-local%3Ap-demo"
        assert params is None
        if payload == {"name": "phase3-demo", "description": "applied"}:
            return {
                "id": "c-local:p-demo",
                "type": "project",
                "name": "phase3-demo",
                "description": "applied",
            }
        if payload == {"name": "phase3-demo", "description": "patched"}:
            return {
                "id": "c-local:p-demo",
                "type": "project",
                "name": "phase3-demo",
                "description": "patched",
            }
        raise AssertionError(f"unexpected Norman PUT payload: {payload}")

    async def patch_json(
        self,
        path: str,
        payload: object = None,
        params: object = None,
    ) -> dict[str, object]:
        """Norman mutation tests do not use native PATCH."""

        raise AssertionError(
            f"unexpected Norman PATCH path: {path} payload={payload} params={params}"
        )

    async def patch_content_json(
        self,
        path: str,
        content: str,
        *,
        content_type: str,
        params: object = None,
    ) -> dict[str, object]:
        """Norman mutation tests do not use raw PATCH bodies."""

        raise AssertionError(
            f"unexpected Norman raw PATCH path: {path} content_type={content_type} params={params}"
        )

    async def delete_json(
        self,
        path: str,
        payload: object = None,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake Norman delete responses."""

        assert path == "/v3/projects/c-local%3Ap-demo"
        assert payload == {"remove": True}
        assert params is None
        return {}


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
async def test_rancher_norman_resource_create_normalizes_created_resource() -> None:
    """Norman generic create should POST to the schema collection path."""

    result = await rancher_norman_resource_create(
        schema_id="project",
        payload_json='{"clusterId": "local", "name": "phase3-demo", "description": "created"}',
        params_json='{"validateOnly": false}',
        instance="work",
        settings=build_settings(),
        client=StubNormanMutationClient(),
    )

    assert result.plane == "norman"
    assert result.operation == "create"
    assert result.request_path == "/v3/projects"
    assert result.resource_id == "c-local:p-demo"


@pytest.mark.asyncio
async def test_rancher_norman_resource_apply_uses_schema_filtered_put_payload() -> None:
    """Norman generic apply should PUT only schema-advertised mutable fields."""

    result = await rancher_norman_resource_apply(
        schema_id="project",
        resource_id="c-local:p-demo",
        payload_json='{"name": "phase3-demo", "description": "applied"}',
        instance="work",
        settings=build_settings(),
        client=StubNormanMutationClient(),
    )

    assert result.operation == "apply"
    assert result.request_method == "PUT"
    assert result.payload["description"] == "applied"


@pytest.mark.asyncio
async def test_rancher_norman_resource_patch_merges_against_mutable_fields_only() -> None:
    """Norman generic patch should merge into a schema-filtered mutable payload."""

    result = await rancher_norman_resource_patch(
        schema_id="project",
        resource_id="c-local:p-demo",
        payload_json='{"description": "patched"}',
        instance="work",
        settings=build_settings(),
        client=StubNormanMutationClient(),
    )

    assert result.operation == "patch"
    assert result.request_method == "PUT"
    assert result.payload["description"] == "patched"


@pytest.mark.asyncio
async def test_rancher_norman_resource_delete_requires_confirmation_phrase() -> None:
    """Norman generic delete should enforce the shared destructive confirmation."""

    with pytest.raises(RancherCapabilityError, match="delete norman project c-local:p-demo"):
        await rancher_norman_resource_delete(
            schema_id="project",
            resource_id="c-local:p-demo",
            confirmation="delete project",
            instance="work",
            settings=build_settings(),
            client=StubNormanMutationClient(),
        )


@pytest.mark.asyncio
async def test_rancher_norman_resource_delete_returns_hint_based_identity_on_empty_body() -> None:
    """Norman generic delete should preserve the requested resource identity on empty responses."""

    result = await rancher_norman_resource_delete(
        schema_id="project",
        resource_id="c-local:p-demo",
        confirmation="delete norman project c-local:p-demo",
        payload_json='{"remove": true}',
        instance="work",
        settings=build_settings(),
        client=StubNormanMutationClient(),
    )

    assert result.operation == "delete"
    assert result.resource_id == "c-local:p-demo"
    assert result.resource_path == "/v3/projects/c-local%3Ap-demo"


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
