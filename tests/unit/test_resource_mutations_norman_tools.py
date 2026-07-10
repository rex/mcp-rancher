"""Generic Norman resource mutation tool tests."""

from __future__ import annotations

import pytest
from _resource_mutations_support import build_settings

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.tools.resource_mutations import (
    rancher_norman_resource_apply,
    rancher_norman_resource_create,
    rancher_norman_resource_delete,
    rancher_norman_resource_patch,
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
