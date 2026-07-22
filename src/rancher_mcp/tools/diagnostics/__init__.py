"""Curated diagnosis-verb tools (M-K7) — pod logs and any-resource events.

Hand-written, not codegen: these are new operator verbs (kubectl-parity
diagnosis), not generic CRUD over one Kubernetes resource type, so they
don't fit the descriptor-driven packs under `tools/pods_services/` and
friends (whose `__init__.py` is itself generated — never hand-edited).
Mirrors the `tools/ops/` curated convenience-tool convention instead.
"""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.diagnostics.pod_logs import rancher_pod_logs, rancher_pod_logs_tool
from rancher_mcp.tools.diagnostics.resource_events import (
    rancher_resource_events,
    rancher_resource_events_tool,
)
from rancher_mcp.tools.support.annotations import READ_ONLY

__all__ = [
    "rancher_pod_logs",
    "rancher_pod_logs_tool",
    "rancher_resource_events",
    "rancher_resource_events_tool",
    "register_diagnostics_tools",
]


def register_diagnostics_tools(mcp: FastMCP) -> None:
    """Register curated diagnosis-verb tools with the FastMCP server."""

    mcp.tool(name="rancher_pod_logs", annotations=READ_ONLY)(rancher_pod_logs_tool)
    mcp.tool(name="rancher_resource_events", annotations=READ_ONLY)(rancher_resource_events_tool)
