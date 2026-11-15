"""Client hints published in each tool's ``_meta``.

What is asserted here is what a client actually receives — the ``tools/list``
entries the SDK builds — not the attribute the pass assigns. A pass that set
the right field on the wrong object, or a field the SDK does not publish, would
satisfy an attribute check and reach no client at all.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from _output_schema_dump_parity_support import build_registered_server
from mcp.server.mcpserver import MCPServer
from mcp.types import Tool

from rancher_mcp.config import clear_toolset_settings_cache
from rancher_mcp.next_step_targets import reset_tool_parameters
from rancher_mcp.server import register_all_tools
from rancher_mcp.tools.support.client_hints import (
    ALWAYS_LOAD_META_KEY,
    ALWAYS_LOAD_TOOLS,
    REQUIRES_USER_INTERACTION_META_KEY,
)

_APPROVAL_SWITCH = "RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE"

#: Characters of name + description + input schema the whole front door may
#: cost. It is paid on every turn of every session the server is connected to,
#: so this is a ceiling to argue with, not a number to nudge: ~750 tokens.
_FRONT_DOOR_BUDGET_CHARS = 3_000
_FRONT_DOOR_MAX_TOOLS = 9


async def _published(mcp: MCPServer) -> dict[str, Tool]:
    return {tool.name: tool for tool in await mcp.list_tools()}


def _upfront_cost(tool: Tool) -> int:
    """What loading one definition upfront costs the model, in characters."""

    return (
        len(tool.name)
        + len(tool.description or "")
        + len(json.dumps(tool.input_schema, separators=(",", ":")))
    )


@pytest.fixture
def _restore_full_registry(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A reduced-profile build repopulates the process-wide next-steps
    registry; put the full one back so later tests see what they expect."""

    yield
    monkeypatch.delenv("RANCHER_EXCLUDE_TOOLS", raising=False)
    monkeypatch.delenv(_APPROVAL_SWITCH, raising=False)
    clear_toolset_settings_cache()
    reset_tool_parameters()
    register_all_tools(MCPServer(name="client-hints-restore-probe"))


async def test_exactly_the_front_door_tools_are_published_as_always_load() -> None:
    published = await _published(build_registered_server())

    marked = {
        name for name, tool in published.items() if (tool.meta or {}).get(ALWAYS_LOAD_META_KEY)
    }

    assert marked == ALWAYS_LOAD_TOOLS


async def test_the_hint_is_the_json_boolean_true() -> None:
    """Claude Code reads these keys strictly; a truthy string is not ``true``."""

    published = await _published(build_registered_server())

    for name in ALWAYS_LOAD_TOOLS:
        assert (published[name].meta or {})[ALWAYS_LOAD_META_KEY] is True


async def test_every_front_door_tool_exists() -> None:
    """A renamed or removed tool would otherwise leave a name here that marks
    nothing, and the front door would shrink without anyone deciding it should."""

    published = await _published(build_registered_server())

    assert ALWAYS_LOAD_TOOLS, "an empty front door makes every other assertion here vacuous"
    assert published.keys() >= ALWAYS_LOAD_TOOLS


async def test_the_front_door_is_read_only() -> None:
    """Upfront-loaded means first-reached-for. Nothing that mutates belongs
    in front of a model that has not looked at the cluster yet."""

    published = await _published(build_registered_server())

    for name in ALWAYS_LOAD_TOOLS:
        annotations = published[name].annotations
        assert annotations is not None and annotations.read_only_hint is True, name


async def test_the_front_door_stays_within_its_context_budget() -> None:
    published = await _published(build_registered_server())

    cost = sum(_upfront_cost(published[name]) for name in ALWAYS_LOAD_TOOLS)

    assert len(ALWAYS_LOAD_TOOLS) <= _FRONT_DOOR_MAX_TOOLS
    assert cost <= _FRONT_DOOR_BUDGET_CHARS, (
        f"the always-load set costs {cost} characters (~{cost // 4} tokens) on every turn of "
        f"every session; the budget is {_FRONT_DOOR_BUDGET_CHARS}. Drop a tool rather than "
        "raise the budget unless the new one is genuinely a first call."
    )


@pytest.mark.usefixtures("_restore_full_registry")
async def test_a_profile_that_drops_a_front_door_tool_just_has_a_smaller_front_door(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dropped = "rancher_resource_events"
    monkeypatch.setenv("RANCHER_EXCLUDE_TOOLS", dropped)
    clear_toolset_settings_cache()
    mcp = MCPServer(name="client-hints-reduced-probe")

    register_all_tools(mcp)
    published = await _published(mcp)

    assert dropped not in published
    marked = {
        name for name, tool in published.items() if (tool.meta or {}).get(ALWAYS_LOAD_META_KEY)
    }
    assert marked == ALWAYS_LOAD_TOOLS - {dropped}


# --- anthropic/requiresUserInteraction --------------------------------------


def _needs_a_person(published: dict[str, Tool]) -> set[str]:
    """Tools published as requiring approval — strictly the JSON boolean
    ``true``, which is the only value Claude Code honours."""

    return {
        name
        for name, tool in published.items()
        if (tool.meta or {}).get(REQUIRES_USER_INTERACTION_META_KEY) is True
    }


async def test_every_destructive_tool_requires_a_person_and_nothing_else_does() -> None:
    published = await _published(build_registered_server())
    destructive = {
        name
        for name, tool in published.items()
        if tool.annotations is not None and tool.annotations.destructive_hint is True
    }

    assert destructive, "no tool is annotated destructive, so this would check nothing"
    assert _needs_a_person(published) == destructive


async def test_every_tool_that_demands_a_confirmation_phrase_also_requires_a_person() -> None:
    """An independent signal, on purpose.

    The pass derives its targets from ``destructiveHint``. If a delete tool
    ever lost that annotation, the check above would still pass — both sides
    of it would shrink together. A ``confirmation`` parameter is the other
    mark of a destructive tool, and it does not move when an annotation does.
    """

    published = await _published(build_registered_server())
    demands_phrase = {
        name
        for name, tool in published.items()
        if "confirmation" in tool.input_schema.get("properties", {})
    }

    assert len(demands_phrase) >= 3, "the delete tools should all demand a confirmation phrase"
    assert demands_phrase <= _needs_a_person(published)


async def test_no_read_only_tool_requires_a_person() -> None:
    """A prompt in front of a read would train the reflex to click through."""

    published = await _published(build_registered_server())

    for name in _needs_a_person(published):
        annotations = published[name].annotations
        assert annotations is not None and annotations.read_only_hint is not True, name


@pytest.mark.usefixtures("_restore_full_registry")
async def test_the_switch_turns_approval_off_and_touches_nothing_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_APPROVAL_SWITCH, "false")
    clear_toolset_settings_cache()
    mcp = MCPServer(name="client-hints-unattended-probe")

    register_all_tools(mcp)
    published = await _published(mcp)

    assert _needs_a_person(published) == set()
    front_door = {
        name for name, tool in published.items() if (tool.meta or {}).get(ALWAYS_LOAD_META_KEY)
    }
    assert front_door == ALWAYS_LOAD_TOOLS
