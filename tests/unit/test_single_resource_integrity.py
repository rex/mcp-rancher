"""A call about one resource never acts on the whole collection.

**The incident this gates.** A resource id is split on ``/`` and its segments
appended to the collection path — and empty segments were dropped. So the id
``/`` appended nothing, and the "resource" was the collection itself::

    rancher_steve_resource_delete(schema_id="persistentvolume", resource_id="/", …)

looked the collection up, found it supported DELETE, and sent ``DELETE`` to
``…/api/v1/persistentvolumes`` — which Kubernetes reads as *deletecollection*:
every PersistentVolume on the cluster. The confirmation phrase and the
approval question both said ``persistentvolume "/"``. The same id made a
generic action invoke a collection-level action. Present in every version
with the generic tools; found by a second independent review on 2026-11-15,
of the fix for the first one's findings.

Three layers, all pinned here:

* an identifier with an **empty segment** — a leading, trailing or doubled
  ``/`` — is refused, before anything is sent;
* the path builder **never returns the collection path** for a resource;
* a reply that **is a collection** is refused where one resource was asked for.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from _output_schema_dump_parity_support import build_registered_server
from _write_guards_support import Answer, observe_call

from rancher_mcp import rate_limit
from rancher_mcp.config import clear_settings_cache, clear_toolset_settings_cache
from rancher_mcp.exceptions import RancherInvalidArgumentError
from rancher_mcp.identifiers import require_safe_identifier
from rancher_mcp.services.resources.contexts import (
    load_norman_resource_context,
    load_steve_resource_context,
)
from rancher_mcp.services.resources.paths import build_resource_path
from rancher_mcp.services.resources.schema import schema_reference_from_payload

_SERVER = build_registered_server()
_EMPTY_SEGMENTS = ["/", "//", "a//b", "/a", "a/", "/a/b", "a/b/"]


def _reset() -> None:
    clear_settings_cache()
    clear_toolset_settings_cache()
    rate_limit.reset_rate_limit_state()


@pytest.fixture(autouse=True)
def _writable_instance(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("RANCHER_READ_ONLY", "false")
    monkeypatch.setenv("RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE", "true")
    _reset()
    yield
    _reset()


# ── The identifier ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", _EMPTY_SEGMENTS)
def test_an_identifier_with_an_empty_segment_names_nothing(value: str) -> None:
    with pytest.raises(RancherInvalidArgumentError, match="`resource_id` has an empty segment"):
        require_safe_identifier("resource_id", value)


def test_an_identifier_longer_than_any_name_is_refused() -> None:
    """Nothing in Rancher or Kubernetes has a name this long; a value that does
    is there to fill a screen."""

    with pytest.raises(RancherInvalidArgumentError, match="`namespace` is longer"):
        require_safe_identifier("namespace", "a" * 254, single_segment=True)
    assert require_safe_identifier("namespace", "a" * 253, single_segment=True)
    # A management-plane id is `namespace:name`, and each part may be that long.
    assert require_safe_identifier("resource_id", f"shop:{'a' * 253}", single_segment=True)
    with pytest.raises(RancherInvalidArgumentError, match="`resource_id` is longer"):
        require_safe_identifier("resource_id", f"shop:{'a' * 254}", single_segment=True)


# ── The path ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("plane", ["norman", "steve"])
@pytest.mark.parametrize("value", _EMPTY_SEGMENTS)
def test_a_resource_path_is_never_the_collection_path(plane: str, value: str) -> None:
    schema = schema_reference_from_payload(
        plane=plane,  # pyright: ignore[reportArgumentType]
        cluster_id="c-prod" if plane == "steve" else None,
        schema_id="persistentvolume",
        payload={"id": "persistentvolume", "pluralName": "persistentvolumes"},
    )

    with pytest.raises(RancherInvalidArgumentError, match="`resource_id`"):
        build_resource_path(schema, resource_id=value)


# ── The reported call, through the request path ─────────────────────────────


@pytest.mark.parametrize("answer", [Answer("accept", proceed=True), None])
@pytest.mark.parametrize("resource_id", ["/", "//"])
async def test_a_delete_of_slash_does_not_delete_the_collection(
    resource_id: str, answer: Answer | None
) -> None:
    """Asked or not: most clients cannot be asked, and then the confirmation
    phrase — which the caller types — was all that stood in the way."""

    seen = await observe_call(
        _SERVER,
        "rancher_steve_resource_delete",
        {
            "schema_id": "persistentvolume",
            "resource_id": resource_id,
            "cluster_id": "c-prod",
            "confirmation": f"delete steve persistentvolume {resource_id}",
        },
        answer=answer,
    )

    assert seen.requests == [], f"something was sent: {seen.requests}"
    assert seen.questions == [], "a person was asked to approve deleting a collection"
    assert seen.is_error and "`resource_id`" in seen.message, seen.envelope


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        (
            "rancher_norman_resource_delete",
            {"schema_id": "token", "resource_id": "/", "confirmation": "delete norman token /"},
        ),
        (
            "rancher_norman_resource_action_invoke",
            {"schema_id": "token", "resource_id": "/", "action_name": "x"},
        ),
        (
            "rancher_steve_resource_action_invoke",
            {"schema_id": "pod", "resource_id": "/", "action_name": "x"},
        ),
        (
            "rancher_steve_resource_patch",
            {"schema_id": "pod", "resource_id": "/", "payload_json": '{"metadata": {"name": "x"}}'},
        ),
        (
            "rancher_steve_resource_apply",
            {"schema_id": "pod", "resource_id": "/", "payload_json": '{"metadata": {"name": "x"}}'},
        ),
        (
            "rancher_norman_resource_patch",
            {"schema_id": "token", "resource_id": "/", "payload_json": '{"description": "x"}'},
        ),
        ("rancher_norman_resource_get", {"schema_id": "token", "resource_id": "/"}),
        ("rancher_steve_resource_get", {"schema_id": "pod", "resource_id": "/"}),
        (
            "rancher_norman_resource_link_follow",
            {"schema_id": "token", "resource_id": "/", "link_name": "self"},
        ),
    ],
)
async def test_no_generic_tool_takes_slash_for_a_resource(
    tool_name: str, arguments: dict[str, object]
) -> None:
    seen = await observe_call(_SERVER, tool_name, arguments)

    writes = [request for request in seen.requests if not request.startswith("GET ")]
    assert writes == [], f"{tool_name} wrote to a collection: {writes}"
    assert not any(request.endswith(("/xs", "/v3/xs")) for request in seen.requests), seen.requests
    assert seen.is_error and "`resource_id`" in seen.message, seen.envelope


# ── A collection that comes back anyway ─────────────────────────────────────


class _Returns:
    """A client whose every GET returns one of two payloads: a schema for a
    schema path, the given reply for anything else."""

    def __init__(self, reply: dict[str, object]) -> None:
        self.reply = reply
        self.paths: list[str] = []

    async def get_json(self, path: str, **_: Any) -> dict[str, object]:
        self.paths.append(path)
        if "/schemas/" in path:
            return {"id": "pod", "pluralName": "pods", "attributes": {"namespaced": True}}
        return self.reply


_COLLECTION: dict[str, object] = {"type": "collection", "resourceType": "pod", "data": []}


async def test_a_collection_is_not_a_resource_on_the_steve_plane() -> None:
    client: Any = _Returns(_COLLECTION)

    with pytest.raises(RancherInvalidArgumentError, match="collection"):
        await load_steve_resource_context(
            cluster_id="c-prod",
            namespace=None,
            schema_id="pod",
            resource_id="kube-system/web-0",
            steve_client=client,
        )


async def test_a_collection_is_not_a_resource_on_the_norman_plane() -> None:
    client: Any = _Returns(_COLLECTION)

    with pytest.raises(RancherInvalidArgumentError, match="collection"):
        await load_norman_resource_context("pod", "p-1", client)


async def test_a_namespace_for_a_cluster_scoped_kind_is_refused() -> None:
    """The request would ignore it, so it could only mislead: an approval
    question that says ``in namespace "scratch"`` about a PersistentVolume."""

    client: Any = _Returns({"id": "pv-1", "type": "persistentvolume"})
    client_schema = {"id": "persistentvolume", "pluralName": "persistentvolumes"}

    async def get_json(path: str, **_: Any) -> dict[str, object]:
        client.paths.append(path)
        return client_schema if "/schemas/" in path else client.reply

    client.get_json = get_json

    with pytest.raises(RancherInvalidArgumentError, match="`namespace`"):
        await load_steve_resource_context(
            cluster_id="c-prod",
            namespace="scratch",
            schema_id="persistentvolume",
            resource_id="pv-1",
            steve_client=client,
        )
    assert not any(path.endswith("pv-1") for path in client.paths), client.paths
