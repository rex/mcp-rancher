"""Enumerate every registered MCP tool into a bounded capture plan.

Pure introspection — registering tools imports the whole ``rancher_mcp``
package but never dials out to a live Rancher instance. Cross-references
``docs/tool-manifest.json`` for read-only classification; the
required/optional parameter split comes from live signature introspection
of each tool's real IMPL function (``resolve_impl_fn``), never the
registered ``_tool`` wrapper — see that function's docstring for why.
"""

from __future__ import annotations

import importlib
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from devtools.capture_sweep.constants import INJECTED_PARAMS
from devtools.capture_sweep.models import ToolPlan


def load_read_only_tool_names(repo_root: Path) -> frozenset[str]:
    """Load the read-only tool name set from the committed tool manifest.

    ``docs/tool-manifest.json`` is generated (``make tool-manifest``) and
    gated fresh (``make check-tool-manifest``), so this is the same
    read_only/destructive classification the rest of the repo trusts —
    no need to re-derive it from FastMCP annotations here.
    """

    manifest_path = repo_root / "docs" / "tool-manifest.json"
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    return frozenset(entry["name"] for entry in manifest["tools"] if entry.get("read_only") is True)


def resolve_impl_fn(wrapper: Callable[..., Any], tool_name: str) -> Callable[..., Any]:
    """Recover the pristine IMPL function behind one registered tool's wrapper.

    CRITICAL / load-bearing: never call a registered tool's ``.fn`` with
    ``settings=``/``instance=`` kwargs directly. By the time all tools are
    registered, ``.fn`` has been progressively reassigned by
    ``apply_sensitive_reveal_audit`` / ``apply_capability_unavailable_translation``
    / ``apply_metrics_to_all_tools`` / ``apply_structured_errors_to_all_tools``
    (see ``rancher_mcp.server.register_all_tools``) and, for codegen'd
    tools, is ultimately the ``*_tool`` wrapper — a public-schema-only
    function that does not declare a ``settings`` parameter at all and
    raises ``TypeError`` if passed one.

    ``functools.wraps`` preserves ``__module__``/``__name__`` through every
    layer of that wrapping, so re-importing the wrapper's defining module
    and looking up the tool's exact name recovers the module-level
    function actually written in the tool module — the real impl, which
    *does* accept ``settings``/``instance`` (with defaults that resolve
    them from the environment when omitted) and is never reassigned by the
    ``apply_*_to_all_tools`` passes. Falls back to *wrapper* itself for the
    handful of tools registered directly with no separate ``_tool`` split.
    """

    module = importlib.import_module(wrapper.__module__)
    return getattr(module, tool_name, wrapper)


def build_capture_plan(mcp: Any, read_only_tools: frozenset[str]) -> list[ToolPlan]:
    """Introspect every registered tool's real IMPL signature into a capture plan."""

    # Reaches into FastMCP's internal tool registry — no public API lists
    # "every registered tool + its raw callable" (rancher_mcp.metrics and
    # rancher_mcp.tools.support.errors do the same for the same reason).
    tools: dict[str, Any] = mcp._tool_manager._tools
    plans: list[ToolPlan] = []
    for name in sorted(tools):
        impl_fn = resolve_impl_fn(tools[name].fn, name)
        required, optional = _split_params(impl_fn)
        plans.append(
            ToolPlan(
                tool=name,
                module=getattr(impl_fn, "__module__", "?"),
                read_only=name in read_only_tools,
                required=required,
                optional=optional,
            )
        )
    return plans


def _split_params(impl_fn: Callable[..., Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split an impl fn's real parameters into (required, optional), sans injected."""

    required: list[str] = []
    optional: list[str] = []
    for param_name, param in inspect.signature(impl_fn).parameters.items():
        if param_name in INJECTED_PARAMS:
            continue
        if param.kind in (param.VAR_KEYWORD, param.VAR_POSITIONAL):
            continue
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            optional.append(param_name)
    return tuple(required), tuple(optional)
