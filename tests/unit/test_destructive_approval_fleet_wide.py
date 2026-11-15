"""Fleet-wide gate: every destructive tool asks a person, and takes no for an answer.

Derived from the annotation a client reads — every registered tool marked
``destructiveHint`` — and driven the way a client drives it, on both protocol
eras: a server request on a legacy connection, a multi-round ``input_required``
result on a modern one. The person on the other end is simulated; every HTTP
request is intercepted, so "the tool did not run" is observed, not inferred.

What is pinned, for each destructive tool:

* a person who declines, dismisses the prompt, or accepts it without ticking
  the box stops the call — nothing is sent — and the refusal says which of the
  three it was;
* a person who agrees lets it through, and that approval is on the audit log;
* a client that cannot be asked is **not** waved through and **not** blocked:
  the call reaches the guards that were always there (never fail open, and
  never break the clients that predate this);
* nobody is asked to approve a call that is going to be refused anyway.

A destructive tool added later with no approval wired in fails the first of
these the day it is annotated: its call goes ahead under a declining client.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from _output_schema_dump_parity_support import build_registered_server
from _write_guards_support import Answer, Observation, observe_call, synthesize_arguments
from mcp.server.mcpserver import MCPServer

from rancher_mcp import rate_limit
from rancher_mcp.clients.management import RancherManagementClient
from rancher_mcp.config import clear_settings_cache, clear_toolset_settings_cache, get_settings
from rancher_mcp.sdk_registry import registered_tools
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.support.annotations import DESTRUCTIVE

_SERVER = build_registered_server()
_TOOLS = {tool.name: tool for tool in registered_tools(_SERVER)}
_DESTRUCTIVE = sorted(
    name
    for name, tool in _TOOLS.items()
    if tool.annotations is not None and tool.annotations.destructive_hint is True
)
_WITH_PHRASE = [
    name for name in _DESTRUCTIVE if "confirmation" in _TOOLS[name].parameters["properties"]
]
_ERAS = ("legacy", "2026-07-28")
_CASES = [(name, era) for name in _DESTRUCTIVE for era in _ERAS]
_PHRASE = re.compile(r"required phrase: '?(?P<phrase>.+?)'?$")


@pytest.fixture(autouse=True)
def _writable_instance_with_budget(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("RANCHER_READ_ONLY", "false")
    # Set, not merely unset: these settings also read a developer's `.env`,
    # and an environment variable is what outranks it.
    monkeypatch.setenv("RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE", "true")
    _reset()
    yield
    _reset()


def _reset() -> None:
    clear_settings_cache()
    clear_toolset_settings_cache()
    rate_limit.reset_rate_limit_state()


async def _valid_arguments(tool_name: str) -> dict[str, object]:
    """Arguments the tool would act on: target named, phrase correct.

    The phrase is learned the way an agent learns it — by calling once without
    it and reading the refusal.
    """

    schema = _TOOLS[tool_name].parameters
    arguments = synthesize_arguments(schema)
    if "namespace" in schema.get("properties", {}):
        arguments["namespace"] = "x"
    if "confirmation" in arguments:
        refusal = await observe_call(_SERVER, tool_name, arguments)
        found = _PHRASE.search(refusal.message)
        assert found, f"{tool_name} did not name its confirmation phrase: {refusal.message!r}"
        arguments["confirmation"] = found["phrase"]
    return arguments


def _approval_records(seen: Observation) -> list[dict[str, object]]:
    return [record for record in seen.audit if record.get("operation") == "approval"]


def test_the_gate_has_real_targets() -> None:
    assert len(_DESTRUCTIVE) >= 5, _DESTRUCTIVE
    assert "rancher_resource_delete" in _DESTRUCTIVE


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        (Answer("decline"), "declined"),
        (Answer("cancel"), "cancelled"),
        (Answer("accept", proceed=False), "unconfirmed"),
    ],
)
@pytest.mark.parametrize(("tool_name", "era"), _CASES)
async def test_a_person_who_does_not_agree_stops_the_call(
    tool_name: str, era: str, answer: Answer, reason: str
) -> None:
    arguments = await _valid_arguments(tool_name)

    seen = await observe_call(_SERVER, tool_name, arguments, answer=answer, mode=era)

    assert len(seen.questions) == 1, f"asked {len(seen.questions)} time(s): {seen.questions}"
    assert seen.requests == [], f"the call went ahead anyway: {seen.requests}"
    assert seen.is_error
    assert seen.error_code == "APPROVAL_DENIED", seen.envelope
    assert seen.envelope is not None
    assert seen.envelope["reason"] == reason
    assert seen.envelope["retryable"] is False
    assert seen.envelope["hint"]
    records = _approval_records(seen)
    assert len(records) == 1
    assert records[0]["outcome"] == "error"
    assert records[0]["error_message"] == reason


@pytest.mark.parametrize(("tool_name", "era"), _CASES)
async def test_a_person_who_agrees_lets_it_through_on_the_record(tool_name: str, era: str) -> None:
    arguments = await _valid_arguments(tool_name)

    seen = await observe_call(
        _SERVER, tool_name, arguments, answer=Answer("accept", proceed=True), mode=era
    )

    assert len(seen.questions) == 1
    assert seen.error_code != "APPROVAL_DENIED", seen.envelope
    assert seen.requests, "an approved call never reached Rancher"
    records = _approval_records(seen)
    assert len(records) == 1
    assert records[0]["outcome"] == "success"
    assert records[0]["tool_name"] == tool_name


@pytest.mark.parametrize(("tool_name", "era"), _CASES)
async def test_the_question_says_what_and_where(tool_name: str, era: str) -> None:
    arguments = await _valid_arguments(tool_name)

    seen = await observe_call(_SERVER, tool_name, arguments, answer=Answer("decline"), mode=era)

    (question,) = seen.questions
    target = str(arguments.get("name") or arguments.get("resource_id"))
    assert f'"{target}"' in question, question
    assert 'Rancher instance "default"' in question, question
    if "cluster_id" in _TOOLS[tool_name].parameters.get("properties", {}):
        # `cluster_id` was left to its default, which is the one to shout about.
        assert "Rancher's own management cluster" in question, question
    if "action_name" in arguments:
        assert f'action "{arguments["action_name"]}"' in question, question


@pytest.mark.parametrize("tool_name", _DESTRUCTIVE)
async def test_a_client_that_cannot_be_asked_is_neither_waved_through_nor_blocked(
    tool_name: str,
) -> None:
    arguments = await _valid_arguments(tool_name)

    seen = await observe_call(_SERVER, tool_name, arguments)

    assert seen.questions == []
    assert seen.error_code != "APPROVAL_DENIED", seen.envelope
    assert seen.requests, "a client without elicitation can no longer use this tool at all"
    assert _approval_records(seen) == []


@pytest.mark.parametrize("tool_name", _DESTRUCTIVE)
async def test_nobody_is_asked_about_a_call_a_read_only_instance_will_refuse(
    tool_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    arguments = await _valid_arguments(tool_name)
    monkeypatch.setenv("RANCHER_READ_ONLY", "true")
    _reset()

    seen = await observe_call(_SERVER, tool_name, arguments, answer=Answer("accept", proceed=True))

    assert seen.questions == [], "a person was asked to approve a call that was then refused"
    assert seen.error_code == "CAPABILITY_ERROR" and "read-only" in seen.message, seen.envelope
    assert seen.requests == []


@pytest.mark.parametrize("tool_name", _WITH_PHRASE)
async def test_nobody_is_asked_about_a_delete_with_the_wrong_phrase(tool_name: str) -> None:
    arguments = await _valid_arguments(tool_name)
    arguments["confirmation"] = "delete it"

    seen = await observe_call(_SERVER, tool_name, arguments, answer=Answer("accept", proceed=True))

    assert seen.questions == []
    assert "required phrase" in seen.message, seen.envelope
    assert seen.requests == []


@pytest.mark.parametrize("tool_name", _DESTRUCTIVE)
async def test_an_operator_can_turn_the_question_off(
    tool_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The unattended pipeline that legitimately deletes: one setting removes
    both this prompt and the Claude Code permission prompt, and leaves every
    other guard where it was."""

    arguments = await _valid_arguments(tool_name)
    monkeypatch.setenv("RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE", "false")
    _reset()

    seen = await observe_call(_SERVER, tool_name, arguments, answer=Answer("decline"))

    assert seen.questions == []
    assert seen.error_code != "APPROVAL_DENIED", seen.envelope
    assert seen.requests


async def test_the_gate_catches_a_destructive_tool_that_asks_nobody() -> None:
    """Non-vacuity: a destructive tool with no approval wired in must look
    different, to the checks above, from one that has it.

    Under a person who declines, such a tool is never told no — it asks nothing
    and goes ahead — which is precisely what
    ``test_a_person_who_does_not_agree_stops_the_call`` asserts cannot happen.
    """

    mcp = MCPServer(name="approval-probe", instructions="probe")

    @mcp.tool(name="rancher_unapproved_delete", annotations=DESTRUCTIVE)
    async def rancher_unapproved_delete(resource_id: str) -> str:  # pyright: ignore[reportUnusedFunction]
        instance_name, instance_config = resolve_instance(get_settings(), None)
        async with RancherManagementClient(instance_name, instance_config) as client:
            await client.delete_json(f"/v3/xs/{resource_id}")
        return "deleted"

    seen = await observe_call(
        mcp, "rancher_unapproved_delete", {"resource_id": "x"}, answer=Answer("decline")
    )

    assert seen.questions == []
    assert seen.requests == ["DELETE /v3/xs/x"]
    assert seen.error_code != "APPROVAL_DENIED"
