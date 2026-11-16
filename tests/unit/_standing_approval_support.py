"""Shared pieces for the standing-approval tests: the server, two people, a call.

Standing approvals live in the server process, so a test that gives one has to
take it away again — ``reset`` does, and each test module runs it before and
after every test.
"""

from __future__ import annotations

import pytest
from _output_schema_dump_parity_support import build_registered_server
from _plausible_arguments_support import plausible_arguments
from _write_guards_support import Answer, Observation, observe_call

from rancher_mcp import rate_limit
from rancher_mcp.config import clear_settings_cache, clear_toolset_settings_cache
from rancher_mcp.sdk_registry import registered_tools
from rancher_mcp.tools.support import standing_approval

SERVER = build_registered_server()
TOOLS = {tool.name: tool for tool in registered_tools(SERVER)}
PATCH = "rancher_steve_resource_patch"
APPLY = "rancher_steve_resource_apply"
CHANGERS = ["rancher_norman_resource_apply", "rancher_norman_resource_patch", APPLY, PATCH]

YES_AND_KEEP_GOING = Answer("accept", proceed=True, keep_going=True)
NO = Answer("decline")


def reset() -> None:
    clear_settings_cache()
    clear_toolset_settings_cache()
    rate_limit.reset_rate_limit_state()
    standing_approval.revoke_all()


def ask_and_offer(monkeypatch: pytest.MonkeyPatch) -> None:
    """A writable instance whose apply and patch tools ask, and offer to keep going."""

    monkeypatch.setenv("RANCHER_READ_ONLY", "false")
    monkeypatch.setenv("RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE", "true")
    monkeypatch.setenv("RANCHER_MCP_APPROVAL_KEEP_GOING_MINUTES", "15")
    reset()


async def call(
    tool_name: str, answer: Answer | None, *, era: str = "2026-07-28", **changed: object
) -> Observation:
    """Call *tool_name* with arguments it would act on, some of them *changed*."""

    arguments = plausible_arguments(tool_name, TOOLS[tool_name].parameters) | changed
    return await observe_call(SERVER, tool_name, arguments, answer=answer, mode=era)


def approvals(seen: Observation) -> list[dict[str, object]]:
    return [record for record in seen.audit if record.get("operation") == "approval"]


def went_through(seen: Observation) -> bool:
    """Whether the change itself was sent, not just the lookups before it."""

    return any(not request.startswith("GET ") for request in seen.requests)
