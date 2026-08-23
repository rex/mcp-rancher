"""Apply a resolved toolset profile to a live FastMCP instance.

``rancher_mcp.toolsets`` owns the family mapping and the pure resolution
logic; this module owns doing something to a real ``FastMCP`` with the
result — the same split every other cross-cutting post-registration pass in
this repo uses (``tools/support/errors.py``, ``.../titles.py``,
``.../capability_unavailable.py``).

Two things happen here, in order:

1. Every disabled tool is removed from the tool manager (``FastMCP.remove_tool``)
   — so it vanishes from ``tools/list``, the whole point of a reduced profile.
2. ``ToolManager.call_tool`` is patched so a direct call to one of those
   removed names still fails with a clear, actionable error naming the tool,
   its family, and the env var to fix it — never FastMCP's generic "Unknown
   tool", which would make a real-but-disabled tool indistinguishable from a
   typo or a tool that never existed at all.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Mapping
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from rancher_mcp.config import get_toolset_settings
from rancher_mcp.toolsets import FamilyRegistration, ResolvedToolset, resolve_active_tools

_logger = structlog.get_logger("rancher_mcp.toolsets")


def _disabled_tool_envelope(
    name: str,
    *,
    family_of: Mapping[str, str],
    excluded: frozenset[str],
    toolsets_raw: str,
) -> str:
    """A structured, already-valid-JSON envelope (matching the shape
    ``tools/support/errors.py`` builds for every other failure this server
    emits) explaining exactly why a real tool refused to run."""

    if name in excluded:
        message = (
            f"Tool {name!r} exists but is excluded by RANCHER_EXCLUDE_TOOLS. "
            "Remove it from that list and restart the server to re-enable it."
        )
        hint = "Edit RANCHER_EXCLUDE_TOOLS to drop this tool name, then restart."
    else:
        family = family_of[name]
        message = (
            f"Tool {name!r} exists but is not enabled by the active RANCHER_TOOLSETS "
            f"profile ({toolsets_raw!r}). It belongs to the {family!r} toolset."
        )
        hint = f"Set RANCHER_TOOLSETS to include {family!r} (or 'all'), then restart the server."
    return json.dumps(
        {
            "error_code": "TOOLSET_NOT_ENABLED",
            "message": message,
            "retryable": False,
            "hint": hint,
        }
    )


def _install_dispatch_gate(
    mcp: FastMCP,
    *,
    family_of: Mapping[str, str],
    excluded: frozenset[str],
    toolsets_raw: str,
) -> None:
    """Make calling a real-but-inactive tool fail with a clear, actionable
    error instead of FastMCP's generic "Unknown tool".

    Patches ``ToolManager.call_tool`` (the same "patch at construction time,
    never at request time" seam ``apply_bare_json_errors`` uses) and is
    installed BEFORE that pass in ``register_all_tools``, so the JSON envelope
    built here — already shaped like every other error envelope this server
    emits — passes through it unchanged rather than being treated as
    unstructured prose.
    """

    # Two-step `Any` coercion, not `manager: Any = mcp._tool_manager` directly
    # — see the matching comment in `rancher_mcp.toolsets.register_families`
    # for why the one-step form still trips pyright strict's
    # `reportPrivateUsage`.
    mcp_any: Any = mcp
    manager = mcp_any._tool_manager
    original_call_tool = manager.call_tool

    @functools.wraps(original_call_tool)
    async def call_tool(name: str, *args: Any, **kwargs: Any) -> Any:
        # `family_of` covers every tool this BUILD can produce; manager._tools
        # is the live, currently-ACTIVE set. A name that is in the former but
        # not the latter is a real, disabled tool — anything else (active, or
        # never registered at all) is left to the original dispatch.
        if name in family_of and name not in manager._tools:
            raise ToolError(
                _disabled_tool_envelope(
                    name, family_of=family_of, excluded=excluded, toolsets_raw=toolsets_raw
                )
            )
        return await original_call_tool(name, *args, **kwargs)

    manager.call_tool = call_tool


def apply_toolset_filter(mcp: FastMCP, registration: FamilyRegistration) -> ResolvedToolset:
    """Resolve the active toolset from settings, remove every disabled tool,
    and install the dispatch gate that explains a disabled call clearly.

    Call once, immediately after ``rancher_mcp.toolsets.register_families`` —
    and BEFORE ``next_step_targets.populate_from_tools``, titles, schema
    compaction, and the ``apply_*`` wrapper chain in ``register_all_tools``,
    so all of those only ever see the active surface (in particular: so no
    response's ``nextSteps`` can ever suggest a tool this profile just
    removed).
    """

    settings = get_toolset_settings()
    resolved = resolve_active_tools(
        all_tools=registration.all_tools,
        family_tools=registration.family_tools,
        toolsets_raw=settings.toolsets,
        include_raw=settings.include_tools,
        exclude_raw=settings.exclude_tools,
    )

    for name in resolved.disabled:
        mcp.remove_tool(name)

    _install_dispatch_gate(
        mcp,
        family_of=registration.family_of,
        excluded=resolved.excluded,
        toolsets_raw=settings.toolsets,
    )

    if resolved.disabled:
        _logger.info(
            "toolset_profile_applied",
            profiles=sorted(resolved.profiles),
            active_count=len(resolved.active),
            disabled_count=len(resolved.disabled),
        )

    return resolved
