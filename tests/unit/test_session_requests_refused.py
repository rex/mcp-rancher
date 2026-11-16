"""A read does not open a session.

**The gap this gates.** Some endpoints act the moment they are reached,
whatever the method. A cluster's ``shell`` link (``wss://…/v3/clusters/<id>?shell=true``)
is a kubectl shell: Rancher creates the pod it runs in *before* it looks at
whether the request is a WebSocket upgrade, so a plain ``GET`` of it — which
is what following a link is — writes to the cluster and then fails. A
Kubernetes ``exec`` runs its ``?command=`` on connecting, before a single
message is sent. Read-only mode judged a request by its method and let both
through. Reported by a second independent review on 2026-11-15; not verified
against a live Rancher.

Pinned here:

* a link whose target is a WebSocket endpoint is not followed;
* no request carries a ``shell`` query parameter, on any method, however it
  was built — and a caller cannot set one;
* a WebSocket to ``/exec``, ``/attach`` or ``/portforward`` counts as a
  mutation whether or not anything is sent over it.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import SecretStr

from rancher_mcp.clients.management import RancherManagementClient
from rancher_mcp.clients.streaming import RancherStreamingClient
from rancher_mcp.exceptions import RancherCapabilityError, RancherInvalidArgumentError
from rancher_mcp.models.discovery import RancherInstanceConfig
from rancher_mcp.services.resource_queries import parse_query_params
from rancher_mcp.services.resources.link_paths import (
    resolve_resource_action_path,
    resolve_resource_link_path,
)


def _config(*, read_only: bool = False) -> RancherInstanceConfig:
    return RancherInstanceConfig(
        url="https://rancher.example.com",
        token=SecretStr("token-x:y"),
        verify_ssl=True,
        read_only=read_only,
    )


@pytest.mark.parametrize(
    "target",
    [
        "wss://rancher.example.com/v3/clusters/local?shell=true",
        "ws://rancher.example.com/v1/management.cattle.io.clusters/local?link=shell",
    ],
)
def test_a_websocket_link_is_not_followed(target: str) -> None:
    payload = {"links": {"shell": target, "self": "https://rancher.example.com/v3/clusters/local"}}

    with pytest.raises(RancherInvalidArgumentError, match="WebSocket endpoint"):
        resolve_resource_link_path(link_name="shell", payload=payload)
    assert resolve_resource_link_path(link_name="self", payload=payload) == "/v3/clusters/local"


def test_a_websocket_action_is_not_invoked_either() -> None:
    payload = {"actions": {"shell": "wss://rancher.example.com/v3/clusters/local?shell=true"}}

    with pytest.raises(RancherInvalidArgumentError, match="WebSocket endpoint"):
        resolve_resource_action_path(action_name="shell", payload=payload)


@pytest.mark.parametrize(
    ("method", "path", "params"),
    [
        ("get_json", "/v3/clusters/local?shell=true", None),
        ("get_json", "/v3/clusters/local", {"shell": "true"}),
        ("post_json", "/v3/clusters/local?shell=true", None),
        ("get_json", "/v3/clusters/local?a=1;shell=true", None),
    ],
)
@respx.mock
async def test_nothing_carrying_shell_is_sent(
    method: str, path: str, params: dict[str, str] | None
) -> None:
    route = respx.route().mock(return_value=httpx.Response(200, json={}))

    async with RancherManagementClient("work", _config()) as client:
        with pytest.raises(RancherInvalidArgumentError, match="`shell`"):
            await getattr(client, method)(path, params=params)

    assert not route.called


@pytest.mark.parametrize("link_name", ["shell", "exec", "attach", "portforward", "Shell"])
def test_a_session_link_is_refused_by_name_whatever_its_scheme(link_name: str) -> None:
    """A deployment that advertises the link as plain ``https`` is still
    advertising a session."""

    payload = {"links": {link_name: "https://rancher.example.com/v3/clusters/local?shell=true"}}

    with pytest.raises(RancherInvalidArgumentError, match="opens a session"):
        resolve_resource_link_path(link_name=link_name, payload=payload)


@pytest.mark.parametrize("source_name", ["params_json", "filters_json"])
@pytest.mark.parametrize("key", ["shell", "link"])
def test_a_caller_cannot_ask_for_a_shell_or_name_a_link(key: str, source_name: str) -> None:
    """``link`` is how Rancher's own link URLs are written on the Kubernetes
    plane, so the transport carries it — when the server supplied it."""

    with pytest.raises(RancherInvalidArgumentError, match=f"`{key}`"):
        parse_query_params(f'{{"{key}": "shell"}}', source_name=source_name)


@pytest.mark.parametrize("subresource", ["exec", "attach", "portforward"])
async def test_a_session_websocket_is_a_mutation_with_nothing_sent(subresource: str) -> None:
    """On a read-only instance it is refused as any write is — with no
    outbound messages at all, which used to make it a read."""

    path = f"/k8s/clusters/c-prod/api/v1/namespaces/shop/pods/web-0/{subresource}"

    async with RancherStreamingClient("work", _config(read_only=True)) as client:
        with pytest.raises(RancherCapabilityError, match="read-only"):
            await client.websocket_capture(path, params={"command": "id"})


async def test_a_read_only_instance_refuses_a_websocket_with_something_to_send() -> None:
    async with RancherStreamingClient("work", _config(read_only=True)) as client:
        with pytest.raises(RancherCapabilityError, match="read-only"):
            await client.websocket_capture("/v1/subscribe", outbound_messages=["x"])
