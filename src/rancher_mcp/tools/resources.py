"""Thin facade for generic resource tool registration and stable imports."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.resource_actions import (
    rancher_norman_resource_action_invoke,
    rancher_norman_resource_action_invoke_tool,
    rancher_norman_resource_link_follow,
    rancher_norman_resource_link_follow_tool,
    rancher_steve_resource_action_invoke,
    rancher_steve_resource_action_invoke_tool,
    rancher_steve_resource_link_follow,
    rancher_steve_resource_link_follow_tool,
)
from rancher_mcp.tools.resource_list_get import (
    rancher_norman_resource_get,
    rancher_norman_resource_get_tool,
    rancher_norman_resource_list,
    rancher_norman_resource_list_tool,
    rancher_steve_resource_get,
    rancher_steve_resource_get_tool,
    rancher_steve_resource_list,
    rancher_steve_resource_list_tool,
)
from rancher_mcp.tools.resource_watch import (
    rancher_steve_resource_watch,
    rancher_steve_resource_watch_tool,
)

__all__ = [
    "rancher_norman_resource_action_invoke",
    "rancher_norman_resource_get",
    "rancher_norman_resource_link_follow",
    "rancher_norman_resource_list",
    "rancher_steve_resource_action_invoke",
    "rancher_steve_resource_get",
    "rancher_steve_resource_link_follow",
    "rancher_steve_resource_list",
    "rancher_steve_resource_watch",
    "register_resource_tools",
]


def register_resource_tools(mcp: FastMCP) -> None:
    """Register generic resource tools with the FastMCP server."""

    mcp.tool(name="rancher_norman_resource_list")(rancher_norman_resource_list_tool)
    mcp.tool(name="rancher_norman_resource_get")(rancher_norman_resource_get_tool)
    mcp.tool(name="rancher_norman_resource_action_invoke")(
        rancher_norman_resource_action_invoke_tool
    )
    mcp.tool(name="rancher_norman_resource_link_follow")(rancher_norman_resource_link_follow_tool)
    mcp.tool(name="rancher_steve_resource_list")(rancher_steve_resource_list_tool)
    mcp.tool(name="rancher_steve_resource_get")(rancher_steve_resource_get_tool)
    mcp.tool(name="rancher_steve_resource_watch")(rancher_steve_resource_watch_tool)
    mcp.tool(name="rancher_steve_resource_action_invoke")(rancher_steve_resource_action_invoke_tool)
    mcp.tool(name="rancher_steve_resource_link_follow")(rancher_steve_resource_link_follow_tool)
