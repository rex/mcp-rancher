"""A request goes to the resource its arguments name — never somewhere else.

**The incident this gates.** Identifiers were percent-quoted into URL paths,
and ``quote("..")`` is ``..``. The HTTP library then resolves dot segments
before sending, so::

    DELETE /api/v1/namespaces/kube-system/pods/..

left the process as ``DELETE /api/v1/namespaces/kube-system``. A delete of a
"pod" named ``..`` deleted its namespace — under a confirmation phrase, an
approval prompt and an audit record that all said "pod". The generic tools
went further: ``resource_id="x/../../clusters/c-prod"`` reached any path on
the Rancher host, and on a read-only instance a GET could be steered to any
in-cluster service through the Kubernetes proxy. Found by an independent
review on 2026-11-15, before the first release that would have advertised the
approval prompt. Every published version before it is affected.

Two layers, both pinned here:

* **the transport** refuses to send any path with a ``.`` or ``..`` segment
  (encoded or not), a fragment, or a control character — whoever built it;
* **identifiers** are refused up front when they contain such a segment or
  characters that have no business in one, so the caller is told which
  argument was wrong and no person is asked to approve it.

The same review's other two ways to bend a call have their own files: the
method (``test_request_method_integrity.py``) and the question a person is
asked (``test_approval_question_integrity.py``).
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
import respx
from _output_schema_dump_parity_support import build_registered_server
from _write_guards_support import Answer, observe_call
from pydantic import SecretStr

from rancher_mcp import rate_limit
from rancher_mcp.clients.management import RancherManagementClient
from rancher_mcp.clients.steve import RancherSteveClient
from rancher_mcp.config import clear_settings_cache, clear_toolset_settings_cache
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.identifiers import require_safe_identifier
from rancher_mcp.models.discovery import RancherInstanceConfig
from rancher_mcp.services.resources.paths import (
    resolve_resource_action_path,
    resolve_resource_link_path,
)

_SERVER = build_registered_server()
_YES = Answer("accept", proceed=True)


def _config() -> RancherInstanceConfig:
    return RancherInstanceConfig(
        url="https://rancher.example.com", token=SecretStr("token-x:y"), verify_ssl=True
    )


@pytest.fixture(autouse=True)
def _writable_instance(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("RANCHER_READ_ONLY", "false")
    monkeypatch.setenv("RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE", "true")
    _reset()
    yield
    _reset()


def _reset() -> None:
    clear_settings_cache()
    clear_toolset_settings_cache()
    rate_limit.reset_rate_limit_state()


# ── The transport ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "/v3/projects/x/../../clusters/c-prod",
        "/k8s/clusters/local/api/v1/namespaces/kube-system/pods/..",
        "/v3/./clusters",
        "/v3/projects/x/%2e%2e/%2E%2E/clusters/c-prod",
        "/v3/schemas/secret#anything",
        "/v3/clusters/c-prod\nX-Injected: 1",
        "//elsewhere.example/v3/clusters",
        "https://elsewhere.example/v3/clusters",
    ],
)
@pytest.mark.parametrize("method", ["get_json", "delete_json"])
@respx.mock
async def test_the_client_will_not_send_a_path_that_resolves_elsewhere(
    method: str, path: str
) -> None:
    route = respx.route().mock(return_value=httpx.Response(200, json={}))

    async with RancherManagementClient("work", _config()) as client:
        with pytest.raises(RancherCapabilityError, match="Refusing to send"):
            await getattr(client, method)(path)

    assert not route.called, f"{method} {path!r} reached the network"


@respx.mock
async def test_the_client_still_sends_ordinary_paths() -> None:
    """Dots inside a name, a colon in a Norman id and a query string are all
    legitimate; only a segment that IS a dot or two is refused."""

    route = respx.route().mock(return_value=httpx.Response(200, json={}))

    async with RancherManagementClient("work", _config()) as client:
        await client.get_json("/v3/projects/c-m-abc:p-xyz")
        await client.get_json("/k8s/clusters/local/api/v1/namespaces/shop/configmaps/app.v1.2")
        await client.post_json("/v3/clusters/c-abc?action=generateKubeconfig")
        await client.get_json("/v3/clusters", params={"limit": 5})

    assert route.call_count == 4


@pytest.mark.parametrize(
    "link",
    ["//elsewhere.example/v3/xs/x?action=x", "https://elsewhere.example/v3/xs/x?action=x"],
)
def test_a_link_in_a_payload_is_followed_on_this_rancher_only(link: str) -> None:
    """A resource's own ``actions`` and ``links`` say where to go next. Whatever
    host one names, only its path is used; a scheme-less ``//host`` used to be
    passed on whole. The transport refuses a host as well, since a URL with a
    scheme is sent to the host it names — token and all."""

    assert resolve_resource_action_path(action_name="x", payload={"actions": {"x": link}}) == (
        "/v3/xs/x?action=x"
    )
    assert resolve_resource_link_path(link_name="x", payload={"links": {"x": link}}) == (
        "/v3/xs/x?action=x"
    )


@respx.mock
async def test_a_cluster_id_cannot_redirect_the_kubernetes_proxy() -> None:
    route = respx.route().mock(return_value=httpx.Response(200, json={}))

    with pytest.raises(RancherCapabilityError, match="cluster_id"):
        async with RancherSteveClient("work", _config(), cluster_id="x/../../v3") as client:
            await client.get_json("/pods")

    assert not route.called


# ── Identifiers ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    ["..", "x/../y", "./x", "a\nb", 'a"b', "a b", "a#b", "a?b", "a\\b", "a%2fb", "a\tb", ""],
)
def test_an_identifier_that_could_name_something_else_is_refused(value: str) -> None:
    with pytest.raises(RancherCapabilityError, match="resource_id"):
        require_safe_identifier("resource_id", value)


@pytest.mark.parametrize(
    "value", ["web", "kube-system/web-0", "c-m-abc123:p-xyz", "app.v1.2", "local", "u-ab_c~1"]
)
def test_ordinary_identifiers_pass(value: str) -> None:
    assert require_safe_identifier("resource_id", value) == value


def test_a_single_segment_identifier_may_not_contain_a_slash() -> None:
    with pytest.raises(RancherCapabilityError, match="schema_id"):
        require_safe_identifier("schema_id", "project/../cluster", single_segment=True)


# ── The reported exploits, through the request path ─────────────────────────


async def test_a_delete_cannot_be_steered_to_another_resource() -> None:
    """Asked about a project; would have deleted a cluster."""

    target = "x/../../clusters/c-prod"

    seen = await observe_call(
        _SERVER,
        "rancher_norman_resource_delete",
        {
            "schema_id": "project",
            "resource_id": target,
            "confirmation": f"delete norman project {target}",
        },
        answer=_YES,
    )

    assert seen.requests == [], f"something was sent: {seen.requests}"
    assert seen.questions == [], "a person was asked to approve a call that names a traversal"
    assert seen.is_error and "resource_id" in seen.message, seen.envelope


async def test_deleting_a_pod_named_dot_dot_does_not_delete_its_namespace() -> None:
    seen = await observe_call(
        _SERVER,
        "rancher_resource_delete",
        {
            "resource_kind": "pod",
            "name": "..",
            "namespace": "kube-system",
            "confirmation": "delete pod .. in namespace kube-system",
        },
        answer=_YES,
    )

    assert seen.requests == [], f"something was sent: {seen.requests}"
    assert seen.questions == []
    assert seen.is_error


async def test_a_read_cannot_be_steered_through_the_kubernetes_proxy() -> None:
    escape = (
        "ns/name/../../../../k8s/clusters/c-prod/api/v1/namespaces/app/services/http:admin:8080"
    )

    seen = await observe_call(
        _SERVER, "rancher_steve_resource_get", {"schema_id": "pod", "resource_id": escape}
    )

    assert not any("c-prod" in request for request in seen.requests), seen.requests
    assert seen.is_error and "resource_id" in seen.message, seen.envelope


@pytest.mark.parametrize("schema_id", ["secret#anything", "project/../cluster", "a b"])
async def test_a_schema_id_is_one_plain_segment(schema_id: str) -> None:
    seen = await observe_call(
        _SERVER, "rancher_norman_resource_get", {"schema_id": schema_id, "resource_id": "x"}
    )

    assert seen.requests == [], seen.requests
    assert seen.is_error and "schema_id" in seen.message, seen.envelope
