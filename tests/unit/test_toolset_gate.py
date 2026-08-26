"""Toolset dispatch-gate tests — calling a tool the active RANCHER_TOOLSETS
profile disabled must fail with a clear, actionable error (never FastMCP's
generic "Unknown tool", which would make a real-but-disabled tool
indistinguishable from a typo), and the whole point of a reduced profile — a
dramatically smaller ``tools/list`` payload — must hold in practice.

Split out of ``test_toolsets.py`` to mirror the production split between
``rancher_mcp.toolsets`` (the mapping + pure resolution logic) and
``rancher_mcp.tools.support.toolset_gate`` (applying a resolved profile to a
live FastMCP) — see both modules' docstrings.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from rancher_mcp.config import clear_toolset_settings_cache
from rancher_mcp.next_step_targets import reset_tool_parameters
from rancher_mcp.sdk_registry import registered_tools
from rancher_mcp.server import register_all_tools
from rancher_mcp.toolsets import CORE_TOOLS, register_families

_FAMILY_MAP = register_families(FastMCP(name="toolset-gate-family-map-probe"))


@pytest.fixture(autouse=True)
def _restore_full_registry_after_each_test(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """See the matching fixture in ``test_toolsets.py`` for the full
    rationale: every test below builds a REDUCED-profile registry, and the
    rest of the suite implicitly depends on ``next_step_targets`` reflecting
    the FULL registry whenever it isn't the one doing the building."""

    yield
    monkeypatch.delenv("RANCHER_TOOLSETS", raising=False)
    monkeypatch.delenv("RANCHER_TOOLS", raising=False)
    monkeypatch.delenv("RANCHER_EXCLUDE_TOOLS", raising=False)
    clear_toolset_settings_cache()
    reset_tool_parameters()
    register_all_tools(FastMCP(name="toolset-gate-restore-probe"))


def _build_profile(
    monkeypatch: pytest.MonkeyPatch,
    *,
    toolsets: str | None = None,
    tools: str | None = None,
    exclude_tools: str | None = None,
) -> FastMCP:
    """Build a real, fully-registered server under a specific env config."""

    for var, value in (
        ("RANCHER_TOOLSETS", toolsets),
        ("RANCHER_TOOLS", tools),
        ("RANCHER_EXCLUDE_TOOLS", exclude_tools),
    ):
        if value is None:
            monkeypatch.delenv(var, raising=False)
        else:
            monkeypatch.setenv(var, value)
    clear_toolset_settings_cache()  # else a prior _build_profile call in this test would be cached

    mcp = FastMCP(name="toolset-gate-probe")
    register_all_tools(mcp)
    return mcp


# ---------------------------------------------------------------------------
# Calling a disabled tool must name the tool, its toolset, and the env var.
# ---------------------------------------------------------------------------


async def test_disabled_tool_call_is_a_clear_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mcp = _build_profile(monkeypatch, toolsets="core")
    disabled = next(iter(_FAMILY_MAP.all_tools - CORE_TOOLS))
    family = _FAMILY_MAP.family_of[disabled]

    with pytest.raises(ToolError) as excinfo:
        await mcp.call_tool(disabled, {})

    payload = json.loads(str(excinfo.value))
    assert payload["error_code"] == "TOOLSET_NOT_ENABLED"
    assert disabled in payload["message"]
    assert family in payload["message"]
    assert "RANCHER_TOOLSETS" in payload["message"]
    assert payload["retryable"] is False


async def test_explicitly_excluded_tool_call_names_the_exclude_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = next(iter(_FAMILY_MAP.all_tools))
    mcp = _build_profile(monkeypatch, toolsets="all", exclude_tools=target)

    with pytest.raises(ToolError) as excinfo:
        await mcp.call_tool(target, {})

    payload = json.loads(str(excinfo.value))
    assert payload["error_code"] == "TOOLSET_NOT_ENABLED"
    assert "RANCHER_EXCLUDE_TOOLS" in payload["message"]


async def test_genuinely_unknown_tool_name_is_unaffected_by_the_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A name with no relationship to any real tool must keep the SDK's
    ordinary "unknown tool" envelope — the toolset gate only ever intercepts
    real, disabled tool names."""

    mcp = _build_profile(monkeypatch, toolsets="core")

    with pytest.raises(ToolError) as excinfo:
        await mcp.call_tool("not_a_real_tool_at_all", {})

    payload = json.loads(str(excinfo.value))
    assert payload["error_code"] == "MCP_ERROR"


async def test_active_tool_call_is_unaffected_by_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate must never interfere with a tool that IS in the active
    profile — only ever with ones that aren't."""

    mcp = _build_profile(monkeypatch, toolsets="core")
    result = await mcp.call_tool("rancher_instance_list", {})
    assert result is not None


# ---------------------------------------------------------------------------
# Payload-size measurement — reuses the wire-shape approach from
# tests/unit/test_context_footprint.py. Duplicated rather than imported: that
# file is itself a ratchet edited independently, and coupling two independent
# gates through a shared helper is exactly what its own docstring avoids.
# ---------------------------------------------------------------------------


def _wire_shape(tool: object) -> dict[str, object]:
    blob: dict[str, object] = {
        "name": tool.name,  # type: ignore[attr-defined]
        "description": tool.description or "",  # type: ignore[attr-defined]
        "inputSchema": tool.parameters,  # type: ignore[attr-defined]
    }
    output_schema = getattr(tool, "output_schema", None)
    if output_schema:
        blob["outputSchema"] = output_schema
    annotations = getattr(tool, "annotations", None)
    if annotations is not None:
        blob["annotations"] = annotations.model_dump(exclude_none=True)
    title = getattr(tool, "title", None)
    if title:
        blob["title"] = title
    return blob


def _tools_list_payload_bytes(mcp: FastMCP) -> int:
    tools = registered_tools(mcp)
    blobs = [_wire_shape(t) for t in tools]
    return len(json.dumps({"tools": blobs}, separators=(",", ":")))


def test_core_profile_tools_list_payload_is_dramatically_smaller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_mcp = _build_profile(monkeypatch, toolsets="all")
    core_mcp = _build_profile(monkeypatch, toolsets="core")

    all_bytes = _tools_list_payload_bytes(all_mcp)
    core_bytes = _tools_list_payload_bytes(core_mcp)

    assert core_bytes < all_bytes * 0.25, (
        f"core ({core_bytes:,} B) is not dramatically smaller than all ({all_bytes:,} B) — "
        "the whole point of a reduced profile is a client that never has to ingest the "
        "full surface just to learn the server exists"
    )
    assert core_bytes < 100_000, f"core profile payload grew to {core_bytes:,} B — investigate"
