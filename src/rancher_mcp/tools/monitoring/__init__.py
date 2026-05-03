"""Curated Rancher monitoring status tool facade."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.monitoring.status import (
    rancher_monitoring_status,
    rancher_monitoring_status_tool,
)

__all__ = [
    "rancher_monitoring_status",
    "register_monitoring_tools",
]


def register_monitoring_tools(mcp: FastMCP) -> None:
    """Register curated monitoring tools with the FastMCP server."""

    mcp.tool(name="rancher_monitoring_status")(rancher_monitoring_status_tool)
