"""Shared data structures for the capture-sweep devtool."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from devtools.capture_sweep.pool import Pool


@dataclass(frozen=True)
class ToolPlan:
    """One registered MCP tool's capture-planning metadata.

    ``required``/``optional`` reflect the real IMPL function's signature
    (see ``enumerator.resolve_impl_fn``) with the always-injected
    ``settings``/``instance`` parameters filtered out — never the
    registered ``_tool`` wrapper's signature, which rejects them.
    """

    tool: str
    module: str
    read_only: bool
    required: tuple[str, ...]
    optional: tuple[str, ...]


@dataclass(frozen=True)
class SweepOutcome:
    """Everything the CLI needs to build a report for one completed sweep."""

    records: list[dict[str, Any]]
    read_only_tools: frozenset[str]
    pool: Pool
