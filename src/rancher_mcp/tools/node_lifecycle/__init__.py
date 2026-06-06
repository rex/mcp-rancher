"""Node lifecycle workflow tools (Track E destructive node ops).

Hand-written (not codegen): these are operator workflows, which the codegen
substrate intentionally does not generate. The first slice ships the
reversible cordon / uncordon pair; drain, drain-status, and delete land in
follow-up slices.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.node_lifecycle.cordon import (
    rancher_node_cordon,
    rancher_node_cordon_tool,
    rancher_node_uncordon,
    rancher_node_uncordon_tool,
)
from rancher_mcp.tools.support.annotations import IDEMPOTENT_WRITE

__all__ = [
    "rancher_node_cordon",
    "rancher_node_cordon_tool",
    "rancher_node_uncordon",
    "rancher_node_uncordon_tool",
    "register_node_lifecycle_tools",
]


def register_node_lifecycle_tools(mcp: FastMCP) -> None:
    """Register node lifecycle tools on *mcp*."""

    mcp.tool(name="rancher_node_cordon", annotations=IDEMPOTENT_WRITE)(rancher_node_cordon_tool)
    mcp.tool(name="rancher_node_uncordon", annotations=IDEMPOTENT_WRITE)(rancher_node_uncordon_tool)
