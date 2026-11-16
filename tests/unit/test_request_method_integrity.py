"""A request is the method it was sent with — a query string cannot overrule it.

**The gap this gates.** Rancher reads two query parameters as instructions
about the request itself. ``?_method=DELETE`` replaces the HTTP method on both
API planes, and ``?action=remove`` makes any management-plane request a
delete (``parseMethod`` / ``parseAction`` in rancher/norman and
rancher/apiserver). The generic tools put a caller's ``params_json`` straight
into the query string. So a list — annotated read-only, and allowed on a
read-only instance — could be made to write; a patch could be made a delete,
with no confirmation phrase and nobody asked; and ``?action=`` on a create was
an action invoke by another name. Every check in this server judged the call
by the method the tool chose. An independent review reported the last of
these on 2026-11-15; the rest turned up closing it. Every version published
before the fix is affected.

Two layers, both pinned here:

* **a caller's query parameters** may not set ``action`` or ``_method`` at
  all, and the caller is told which argument was wrong;
* **the transport** sends nothing carrying ``_method``, and ``action`` only
  on a POST — whoever built the request.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping

import httpx
import pytest
import respx
from _output_schema_dump_parity_support import build_registered_server
from _plausible_arguments_support import plausible_arguments
from _write_guards_support import observe_call
from pydantic import SecretStr

from rancher_mcp import rate_limit
from rancher_mcp.clients.management import RancherManagementClient
from rancher_mcp.clients.streaming import RancherStreamingClient
from rancher_mcp.config import clear_settings_cache, clear_toolset_settings_cache
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.models.discovery import RancherInstanceConfig
from rancher_mcp.sdk_registry import registered_tools
from rancher_mcp.services.resource_queries import parse_query_params

_SERVER = build_registered_server()
_TOOLS = {tool.name: tool for tool in registered_tools(_SERVER)}
_KEYS = ("_method", "action", "shell")

# Every argument, on every tool, through which a caller names query parameters.
_TARGETS = sorted(
    (name, argument)
    for name, tool in _TOOLS.items()
    for argument in ("params_json", "filters_json")
    if argument in tool.parameters.get("properties", {})
)


def _config() -> RancherInstanceConfig:
    return RancherInstanceConfig(
        url="https://rancher.example.com", token=SecretStr("token-x:y"), verify_ssl=True
    )


def _reset() -> None:
    clear_settings_cache()
    clear_toolset_settings_cache()
    rate_limit.reset_rate_limit_state()


@pytest.fixture(autouse=True)
def _writable_instance(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("RANCHER_READ_ONLY", "false")
    _reset()
    yield
    _reset()


# ── The transport ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "path", "params"),
    [
        ("get_json", "/v3/clusters/c-prod?_method=DELETE", None),
        ("get_json", "/v3/clusters/c-prod", {"_method": "DELETE"}),
        ("get_json", "/v3/clusters/c-prod?%5Fmethod=DELETE", None),
        ("get_json", "/v3/tokens?limit=5&_method=POST", None),
        ("post_json", "/v3/clusters/c-prod?action=x", {"_method": "DELETE"}),
        ("put_json", "/v3/clusters/c-prod", {"_method": "DELETE"}),
        ("get_json", "/v3/clusters/c-prod?action=remove", None),
        ("get_json", "/v3/clusters/c-prod", {"action": "remove"}),
        ("put_json", "/v3/clusters/c-prod", {"action": "remove"}),
        ("delete_json", "/v3/clusters/c-prod", {"action": "x"}),
        # `;` separated parameters too, to Go before 1.17
        ("get_json", "/v3/globalroles/admin?a=1;_method=DELETE", None),
        ("get_json", "/v3/clusters/c-prod?a=1;action=remove", None),
        ("get_json", "/v3/clusters/c-prod?a=1;%5Fmethod=DELETE", None),
    ],
)
@respx.mock
async def test_the_client_will_not_send_what_rancher_would_read_as_another_request(
    method: str, path: str, params: Mapping[str, str] | None
) -> None:
    route = respx.route().mock(return_value=httpx.Response(200, json={}))

    async with RancherManagementClient("work", _config()) as client:
        with pytest.raises(RancherCapabilityError, match="Refusing to send"):
            await getattr(client, method)(path, params=params)

    assert not route.called, f"{method} {path!r} {params} reached the network"


@respx.mock
async def test_an_action_still_goes_out_on_the_post_that_invokes_it() -> None:
    route = respx.route().mock(return_value=httpx.Response(200, json={}))

    async with RancherManagementClient("work", _config()) as client:
        await client.post_json("/v3/clusters/c-abc?action=rotateCertificates", payload={})
        await client.post_json("/v3/clusters/c-abc", params={"action": "rotateCertificates"})

    assert route.call_count == 2


@pytest.mark.parametrize("key", _KEYS)
@respx.mock
async def test_the_streaming_client_takes_the_same_look(key: str) -> None:
    route = respx.route().mock(return_value=httpx.Response(200, text=""))

    async with RancherStreamingClient("work", _config()) as client:
        with pytest.raises(RancherCapabilityError, match="Refusing to send"):
            await client.stream_json_lines("/v1/pods", params={"watch": "true", key: "DELETE"})

    assert not route.called


# ── What a caller may put in a query ────────────────────────────────────────


@pytest.mark.parametrize("key", ["action", "_method", "Action", " _METHOD "])
@pytest.mark.parametrize("source_name", ["params_json", "filters_json"])
def test_a_caller_may_not_set_either_parameter(key: str, source_name: str) -> None:
    with pytest.raises(RancherCapabilityError, match=source_name):
        parse_query_params(json.dumps({key: "DELETE"}), source_name=source_name)


def test_ordinary_query_parameters_still_pass() -> None:
    assert parse_query_params('{"limit": 5, "actions": "x", "method": "GET"}') == {
        "limit": 5,
        "actions": "x",
        "method": "GET",
    }


# ── Every tool, through the request path ────────────────────────────────────


def test_the_gate_has_real_targets() -> None:
    """Canary: a broken registry would leave the loop below with nothing to do."""

    assert len(_TARGETS) >= 10, _TARGETS
    assert ("rancher_norman_resource_list", "params_json") in _TARGETS
    assert ("rancher_norman_resource_list", "filters_json") in _TARGETS
    assert ("rancher_steve_resource_patch", "params_json") in _TARGETS


async def test_the_gate_can_see_a_query_parameter() -> None:
    """Non-vacuity: the check below reads ``query_keys``, so that has to be
    something an ordinary parameter actually shows up in."""

    seen = await observe_call(
        _SERVER,
        "rancher_norman_resource_list",
        {"schema_id": "project", "params_json": '{"name": "shop"}'},
    )

    assert "name" in seen.query_keys, (seen.requests, seen.query_keys, seen.envelope)


async def test_no_tool_lets_a_caller_rewrite_the_request() -> None:
    offenders: list[str] = []
    unnamed: list[str] = []
    named = 0
    for tool_name, argument in _TARGETS:
        for key in _KEYS:
            rate_limit.reset_rate_limit_state()
            arguments = plausible_arguments(tool_name, _TOOLS[tool_name].parameters)
            arguments[argument] = json.dumps({key: "DELETE"})

            seen = await observe_call(_SERVER, tool_name, arguments)

            if key in seen.query_keys or not seen.is_error:
                offenders.append(f"{tool_name} {argument}={{{key!r}: …}} sent {seen.requests}")
            if f"`{key}`" in seen.message:
                named += 1
            else:
                unnamed.append(f"{tool_name} {argument} {key}: {seen.message!r}")

    assert not offenders, (
        "these tools sent a request carrying a parameter Rancher reads as a change of "
        "method or an action invoke:\n  " + "\n  ".join(offenders)
    )
    assert not unnamed, (
        f"only {named} refusals named the parameter. These calls were refused for some other "
        "reason, so they say nothing about the parameter:\n  " + "\n  ".join(unnamed)
    )


async def test_a_read_only_instance_cannot_be_written_through_a_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The case that matters most: the list tools are the ones a read-only
    instance leaves open."""

    monkeypatch.setenv("RANCHER_READ_ONLY", "true")
    _reset()

    seen = await observe_call(
        _SERVER,
        "rancher_norman_resource_list",
        {"schema_id": "token", "params_json": '{"_method": "POST"}'},
    )

    assert "_method" not in seen.query_keys, seen.requests
    assert all(request.startswith("GET ") for request in seen.requests), seen.requests
    assert seen.is_error and "_method" in seen.message, seen.envelope


async def test_an_action_cannot_be_slipped_into_a_create() -> None:
    """The reported case: ``?action=`` on a collection POST is an action
    invoke, one that would skip the approval the action tools require."""

    seen = await observe_call(
        _SERVER,
        "rancher_norman_resource_create",
        {
            "schema_id": "token",
            "payload_json": '{"description": "x"}',
            "params_json": '{"action": "logout"}',
        },
    )

    assert not any(request.startswith("POST") for request in seen.requests), seen.requests
    assert seen.is_error and "must not set `action`" in seen.message, seen.envelope
    assert seen.envelope is not None and seen.envelope["reason"] == "invalid_argument"
