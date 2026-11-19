"""Fleet-wide gate: a tool that can replace or strip a resource asks a person.

**The gap this gates.** The five tools annotated destructive ask before they
act. The generic apply and patch tools did not — and they can do most of what
a delete can: replace a spec, drop fields, scale to zero, remove finalizers.
Decided on 2026-11-15: they ask by default, and a person may let the agent
continue (``test_standing_approval.py``).

Derived from the registry, not from a list: every registered tool that takes
an approval and is *not* annotated destructive. Driven the way a client drives
it, on both protocol eras, with every HTTP request intercepted. For each:

* a person who declines, dismisses the prompt, or accepts it without ticking
  the first box stops the call, and nothing is sent;
* a person who agrees lets it through, and that is on the audit log;
* the question shows the change itself — the payload — and where it lands;
* a client that cannot be asked is neither waved through nor blocked;
* nobody is asked about a call that will be refused anyway;
* an operator can turn the question off.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Iterator

import pytest
from _output_schema_dump_parity_support import build_registered_server
from _plausible_arguments_support import plausible_arguments
from _write_guards_support import Answer, Observation, observe_call

from rancher_mcp import rate_limit
from rancher_mcp.config import clear_settings_cache, clear_toolset_settings_cache
from rancher_mcp.sdk_registry import RegisteredTool, registered_tools
from rancher_mcp.tools.support import standing_approval

_SERVER = build_registered_server()
_TOOLS = {tool.name: tool for tool in registered_tools(_SERVER)}


def _asks(tool: RegisteredTool) -> bool:
    return "approval" in inspect.signature(tool.fn).parameters


def _is_destructive(tool: RegisteredTool) -> bool:
    return tool.annotations is not None and tool.annotations.destructive_hint is True


_CHANGERS = sorted(
    name for name, tool in _TOOLS.items() if _asks(tool) and not _is_destructive(tool)
)
_ERAS = ("legacy", "2026-07-28")
_CASES = [(name, era) for name in _CHANGERS for era in _ERAS]
_CANARY = "hunter2"  # a value that must never be shown


def _reset() -> None:
    clear_settings_cache()
    clear_toolset_settings_cache()
    rate_limit.reset_rate_limit_state()
    standing_approval.revoke_all()


@pytest.fixture(autouse=True)
def _writable_instance_that_asks(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("RANCHER_READ_ONLY", "false")
    monkeypatch.setenv("RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE", "true")
    monkeypatch.setenv("RANCHER_MCP_APPROVAL_KEEP_GOING_MINUTES", "15")
    _reset()
    yield
    _reset()


def _arguments(tool_name: str) -> dict[str, object]:
    return plausible_arguments(tool_name, _TOOLS[tool_name].parameters)


def _approvals(seen: Observation) -> list[dict[str, object]]:
    return [record for record in seen.audit if record.get("operation") == "approval"]


def _writes(seen: Observation) -> list[str]:
    return [request for request in seen.requests if not request.startswith("GET ")]


def test_the_gate_has_real_targets() -> None:
    assert _CHANGERS == [
        "rancher_norman_resource_apply",
        "rancher_norman_resource_patch",
        "rancher_steve_resource_apply",
        "rancher_steve_resource_patch",
    ]


def test_every_destructive_tool_asks_too() -> None:
    """The other gate derives its targets from the annotation; this is the
    statement that the two sets together are all the tools that ask."""

    silent = sorted(
        name for name, tool in _TOOLS.items() if _is_destructive(tool) and not _asks(tool)
    )
    assert silent == []


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        (Answer("decline"), "declined"),
        (Answer("cancel"), "cancelled"),
        (Answer("accept", proceed=False), "unconfirmed"),
        (Answer("accept", proceed=False, keep_going=True), "unconfirmed"),
    ],
)
@pytest.mark.parametrize(("tool_name", "era"), _CASES)
async def test_a_person_who_does_not_agree_stops_the_change(
    tool_name: str, era: str, answer: Answer, reason: str
) -> None:
    seen = await observe_call(_SERVER, tool_name, _arguments(tool_name), answer=answer, mode=era)

    assert len(seen.questions) == 1, seen.questions
    assert seen.requests == [], f"the change went ahead anyway: {seen.requests}"
    assert seen.error_code == "APPROVAL_DENIED", seen.envelope
    assert seen.envelope is not None and seen.envelope["reason"] == reason
    (record,) = _approvals(seen)
    assert record["outcome"] == "error" and record["error_message"] == reason


@pytest.mark.parametrize(("tool_name", "era"), _CASES)
async def test_a_person_who_agrees_lets_it_through_on_the_record(tool_name: str, era: str) -> None:
    seen = await observe_call(
        _SERVER, tool_name, _arguments(tool_name), answer=Answer("accept", proceed=True), mode=era
    )

    assert len(seen.questions) == 1
    assert seen.error_code != "APPROVAL_DENIED", seen.envelope
    assert _writes(seen), f"an approved change never reached Rancher: {seen.requests}"
    (record,) = _approvals(seen)
    assert record["outcome"] == "success"
    assert record["tool_name"] == tool_name
    assert record["approval_basis"] == "asked"
    assert "standing_minutes" not in record, "one yes was recorded as a standing approval"


@pytest.mark.parametrize(("tool_name", "era"), _CASES)
async def test_the_question_shows_the_change_and_where_it_lands(tool_name: str, era: str) -> None:
    seen = await observe_call(
        _SERVER, tool_name, _arguments(tool_name), answer=Answer("decline"), mode=era
    )

    (question,) = seen.questions
    assert ' x "x"' in question, question
    assert 'Rancher instance "default"' in question
    assert 'Payload: {"metadata": {"name": "x"}}' in question
    if "cluster_id" in _TOOLS[tool_name].parameters.get("properties", {}):
        assert "Rancher's own management cluster" in question, question


@pytest.mark.parametrize("tool_name", _CHANGERS)
async def test_the_question_does_not_show_what_a_secret_holds(tool_name: str) -> None:
    """A patch does not say what it patches, so each tool has to tell the
    display — or a Secret's ``data`` is printed like a ConfigMap's."""

    payload = json.dumps({"data": {"db-pass": _CANARY}})
    secret = _arguments(tool_name) | {"schema_id": "secret", "payload_json": payload}
    config = _arguments(tool_name) | {"schema_id": "configmap", "payload_json": payload}

    hidden = await observe_call(_SERVER, tool_name, secret, answer=Answer("decline"))
    shown = await observe_call(_SERVER, tool_name, config, answer=Answer("decline"))

    assert '"db-pass": "********"' in hidden.questions[0], hidden.questions[0]
    assert _CANARY not in hidden.questions[0]
    assert _CANARY in shown.questions[0]


async def test_an_apply_under_another_field_manager_says_so() -> None:
    """Server-side apply removes whatever the named manager owns and the
    payload leaves out. Applied as ``helm``, a three-line payload can strip a
    release bare — and nothing in the payload shows it."""

    tool_name = "rancher_steve_resource_apply"
    borrowed = await observe_call(
        _SERVER,
        tool_name,
        _arguments(tool_name) | {"field_manager": "helm", "force": True},
        answer=Answer("decline"),
    )
    own = await observe_call(_SERVER, tool_name, _arguments(tool_name), answer=Answer("decline"))

    assert 'With query options: {"fieldManager": "helm", "force": true}' in borrowed.questions[0]
    assert "fieldManager" not in own.questions[0]


@pytest.mark.parametrize("tool_name", _CHANGERS)
async def test_a_client_that_cannot_be_asked_is_neither_waved_through_nor_blocked(
    tool_name: str,
) -> None:
    seen = await observe_call(_SERVER, tool_name, _arguments(tool_name))

    assert seen.questions == []
    assert seen.error_code != "APPROVAL_DENIED", seen.envelope
    assert _writes(seen), "a client without elicitation can no longer use this tool at all"
    assert _approvals(seen) == []


@pytest.mark.parametrize("tool_name", _CHANGERS)
async def test_nobody_is_asked_about_a_change_a_read_only_instance_will_refuse(
    tool_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RANCHER_READ_ONLY", "true")
    _reset()

    seen = await observe_call(
        _SERVER, tool_name, _arguments(tool_name), answer=Answer("accept", proceed=True)
    )

    assert seen.questions == [], "a person was asked to approve a call that was then refused"
    assert seen.error_code == "CAPABILITY_ERROR" and "read-only" in seen.message, seen.envelope
    assert seen.requests == []


@pytest.mark.parametrize("tool_name", _CHANGERS)
async def test_nobody_is_asked_about_a_change_with_no_payload(tool_name: str) -> None:
    arguments = _arguments(tool_name) | {"payload_json": "{}"}

    seen = await observe_call(_SERVER, tool_name, arguments, answer=Answer("accept", proceed=True))

    assert seen.questions == []
    assert seen.requests == []
    assert seen.is_error and "payload_json" in seen.message, seen.envelope


@pytest.mark.parametrize("tool_name", _CHANGERS)
async def test_an_operator_can_turn_the_question_off(
    tool_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE", "false")
    _reset()

    seen = await observe_call(_SERVER, tool_name, _arguments(tool_name), answer=Answer("decline"))

    assert seen.questions == []
    assert seen.error_code != "APPROVAL_DENIED", seen.envelope
    assert _writes(seen)
