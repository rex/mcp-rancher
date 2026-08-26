"""Toolset-profile tests (RANCHER_TOOLSETS / RANCHER_TOOLS / RANCHER_EXCLUDE_TOOLS).

Builds the real registry via ``register_families``/``register_all_tools`` —
never a hand-maintained tool inventory — so these tests catch a genuine
regression in ``toolsets.py`` rather than merely re-asserting its own data.
``_FAMILY_MAP`` is built once, at import time, directly from
``register_families`` (bypassing ``apply_toolset_filter`` entirely) so it is
an independent ground truth the filtering tests below can be checked against.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from mcp.server.fastmcp import FastMCP

from rancher_mcp.config import clear_toolset_settings_cache
from rancher_mcp.exceptions import ConfigurationError
from rancher_mcp.next_step_targets import reset_tool_parameters
from rancher_mcp.sdk_registry import registered_tools
from rancher_mcp.server import register_all_tools
from rancher_mcp.toolsets import (
    CORE_TOOLS,
    FAMILY_REGISTRARS,
    register_families,
    resolve_active_tools,
)

_FAMILY_MAP = register_families(FastMCP(name="toolsets-family-map-probe"))


@pytest.fixture(autouse=True)
def _restore_full_registry_after_each_test(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Several tests below build a REDUCED-profile registry, which leaves the
    module-level ``next_step_targets`` global populated with that reduced
    view for the rest of the process. Other test files (in particular
    ``test_next_steps_registry_gate.py``, whose own registry fixture is built
    ONCE at collection time and never refreshed per-test) implicitly depend
    on that global reflecting the FULL registry whenever they aren't the one
    doing the building. Restore it after every test in this file so nothing
    that runs afterward — regardless of execution order — ever observes a
    reduced profile it didn't ask for.
    """

    yield
    monkeypatch.delenv("RANCHER_TOOLSETS", raising=False)
    monkeypatch.delenv("RANCHER_TOOLS", raising=False)
    monkeypatch.delenv("RANCHER_EXCLUDE_TOOLS", raising=False)
    clear_toolset_settings_cache()
    reset_tool_parameters()
    register_all_tools(FastMCP(name="toolsets-restore-probe"))


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

    mcp = FastMCP(name="toolsets-probe")
    register_all_tools(mcp)
    return mcp


def _active_names(mcp: FastMCP) -> set[str]:
    return {tool.name for tool in registered_tools(mcp)}


# ---------------------------------------------------------------------------
# The family map itself — ground truth the rest of this file leans on.
# ---------------------------------------------------------------------------


def test_family_map_has_a_healthy_tool_count() -> None:
    """Canary against a silently-empty sweep (mirrors the next-steps registry
    gate's own canary): if registration broke, every check below would
    vacuously pass."""

    assert len(_FAMILY_MAP.all_tools) > 100
    assert len(FAMILY_REGISTRARS) >= 30


def test_families_are_disjoint_and_cover_all_tools() -> None:
    seen: set[str] = set()
    overlap: set[str] = set()
    for tools in _FAMILY_MAP.family_tools.values():
        overlap |= seen & tools
        seen |= tools
    assert not overlap, f"tool(s) registered by more than one family: {sorted(overlap)}"
    assert seen == _FAMILY_MAP.all_tools


# ---------------------------------------------------------------------------
# Pure resolution logic — no FastMCP construction needed.
# ---------------------------------------------------------------------------


def test_resolve_unknown_profile_name_fails_loudly() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        resolve_active_tools(
            all_tools=_FAMILY_MAP.all_tools,
            family_tools=_FAMILY_MAP.family_tools,
            toolsets_raw="not_a_real_profile",
            include_raw="",
            exclude_raw="",
        )
    message = str(excinfo.value)
    assert "not_a_real_profile" in message
    assert "core" in message and "all" in message  # lists the valid profiles


def test_resolve_default_all_is_the_full_registry() -> None:
    resolved = resolve_active_tools(
        all_tools=_FAMILY_MAP.all_tools,
        family_tools=_FAMILY_MAP.family_tools,
        toolsets_raw="all",
        include_raw="",
        exclude_raw="",
    )
    assert resolved.active == _FAMILY_MAP.all_tools
    assert not resolved.disabled


def test_resolve_combines_multiple_profiles() -> None:
    resolved = resolve_active_tools(
        all_tools=_FAMILY_MAP.all_tools,
        family_tools=_FAMILY_MAP.family_tools,
        toolsets_raw="core,storage",
        include_raw="",
        exclude_raw="",
    )
    assert resolved.active >= CORE_TOOLS
    assert resolved.active >= _FAMILY_MAP.family_tools["storage"]


def test_resolve_include_unknown_tool_name_fails_loudly() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        resolve_active_tools(
            all_tools=_FAMILY_MAP.all_tools,
            family_tools=_FAMILY_MAP.family_tools,
            toolsets_raw="core",
            include_raw="rancher_this_tool_does_not_exist",
            exclude_raw="",
        )
    assert "rancher_this_tool_does_not_exist" in str(excinfo.value)


def test_resolve_exclude_unknown_tool_name_is_a_harmless_noop() -> None:
    """Unlike RANCHER_TOOLS, an unknown RANCHER_EXCLUDE_TOOLS entry must NOT
    raise — excluding something that was never present is a no-op, and
    staying lenient keeps an exclude list portable across builds."""

    resolved = resolve_active_tools(
        all_tools=_FAMILY_MAP.all_tools,
        family_tools=_FAMILY_MAP.family_tools,
        toolsets_raw="core",
        include_raw="",
        exclude_raw="rancher_this_tool_does_not_exist_either",
    )
    assert resolved.active == CORE_TOOLS


def test_resolve_exclude_wins_over_include_for_the_same_tool() -> None:
    target = next(iter(_FAMILY_MAP.family_tools["storage"]))
    resolved = resolve_active_tools(
        all_tools=_FAMILY_MAP.all_tools,
        family_tools=_FAMILY_MAP.family_tools,
        toolsets_raw="core",
        include_raw=target,
        exclude_raw=target,
    )
    assert target not in resolved.active


# ---------------------------------------------------------------------------
# End-to-end: register_all_tools under real env config.
# ---------------------------------------------------------------------------


def test_default_all_profile_exposes_the_full_unfiltered_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repo owner's ruling: default is `all`, full capability, nothing
    silently trimmed. Asserted against the independently-built family map so
    this cannot silently shrink."""

    mcp = _build_profile(monkeypatch, toolsets=None)
    assert _active_names(mcp) == _FAMILY_MAP.all_tools


def test_named_family_profile_is_a_strict_correct_subset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mcp = _build_profile(monkeypatch, toolsets="storage")
    active = _active_names(mcp)
    assert active == _FAMILY_MAP.family_tools["storage"]
    assert active < _FAMILY_MAP.all_tools


def test_core_tools_all_exist_in_the_real_registry() -> None:
    """A typo'd CORE_TOOLS entry must fail THIS test, not silently shrink the
    profile at runtime."""

    assert CORE_TOOLS
    unknown = CORE_TOOLS - _FAMILY_MAP.all_tools
    assert not unknown, f"CORE_TOOLS references tool(s) absent from the registry: {sorted(unknown)}"


def test_core_profile_is_non_empty_coherent_and_roughly_thirty_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mcp = _build_profile(monkeypatch, toolsets="core")
    active = _active_names(mcp)
    assert active == CORE_TOOLS
    assert 20 <= len(active) <= 45


def test_unknown_toolsets_profile_fails_loudly_at_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RANCHER_TOOLSETS", "bogus_profile_xyz")
    monkeypatch.delenv("RANCHER_TOOLS", raising=False)
    monkeypatch.delenv("RANCHER_EXCLUDE_TOOLS", raising=False)
    clear_toolset_settings_cache()

    with pytest.raises(ConfigurationError) as excinfo:
        register_all_tools(FastMCP(name="toolsets-unknown-probe"))
    assert "bogus_profile_xyz" in str(excinfo.value)


def test_rancher_tools_force_includes_on_top_of_the_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extra = next(iter(_FAMILY_MAP.family_tools["workloads"]))
    mcp = _build_profile(monkeypatch, toolsets="storage", tools=extra)
    active = _active_names(mcp)
    assert active == _FAMILY_MAP.family_tools["storage"] | {extra}


def test_rancher_exclude_tools_removes_and_wins_over_include(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = next(iter(_FAMILY_MAP.family_tools["storage"]))
    # Force-include AND exclude the exact same tool: exclude must still win.
    mcp = _build_profile(monkeypatch, toolsets="storage", tools=target, exclude_tools=target)
    active = _active_names(mcp)
    assert target not in active
    assert active == _FAMILY_MAP.family_tools["storage"] - {target}


# ---------------------------------------------------------------------------
# next_steps must never suggest a tool outside the active profile.
# ---------------------------------------------------------------------------


def test_next_steps_drops_suggestions_outside_the_active_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rancher_mcp.models.ops.cluster_health import ClusterHealthCheck

    _build_profile(monkeypatch, toolsets="core")  # populates next_step_targets to CORE_TOOLS only

    non_core = next(iter(_FAMILY_MAP.all_tools - CORE_TOOLS))
    instance = ClusterHealthCheck(
        instance="w",
        cluster_id="c-x",
        cluster_name="n",
        healthy=True,
        suggested_next_steps=["rancher_nodes_list", non_core],
    )
    suggested = {entry["tool"] for entry in instance.next_steps}

    assert "rancher_nodes_list" in suggested  # in CORE_TOOLS: survives
    assert non_core not in suggested  # outside the active profile: dropped


def test_next_steps_unfiltered_when_registry_never_populated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Back-compat guardrail: a model built with no FastMCP registry in the
    process at all (e.g. a bare unit test) must keep emitting every declared
    suggestion, exactly as before this feature existed."""

    from rancher_mcp.models.ops.cluster_health import ClusterHealthCheck

    reset_tool_parameters()  # simulate "never populated in this process"
    instance = ClusterHealthCheck(
        instance="w",
        cluster_id="c-x",
        cluster_name="n",
        healthy=True,
        suggested_next_steps=["rancher_nodes_list"],
    )
    assert {entry["tool"] for entry in instance.next_steps} == {"rancher_nodes_list"}


# Dispatch-gate behavior (calling a disabled tool) and the payload-size
# measurement live in tests/unit/test_toolset_gate.py, mirroring the
# production split between rancher_mcp.toolsets and
# rancher_mcp.tools.support.toolset_gate.
