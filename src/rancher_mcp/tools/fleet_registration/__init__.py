"""Curated Rancher Fleet and registration tool facade."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.fleet_registration.cluster_registration_tokens import (
    rancher_cluster_registration_token_get,
    rancher_cluster_registration_token_get_tool,
    rancher_cluster_registration_tokens_list,
    rancher_cluster_registration_tokens_list_tool,
)
from rancher_mcp.tools.fleet_registration.fleet_workspaces import (
    rancher_fleet_workspace_get,
    rancher_fleet_workspace_get_tool,
    rancher_fleet_workspaces_list,
    rancher_fleet_workspaces_list_tool,
)
from rancher_mcp.tools.support.annotations import READ_ONLY

__all__ = [
    "rancher_cluster_registration_token_get",
    "rancher_cluster_registration_tokens_list",
    "rancher_fleet_workspace_get",
    "rancher_fleet_workspaces_list",
    "register_fleet_registration_tools",
]


def register_fleet_registration_tools(mcp: FastMCP) -> None:
    """Register curated Fleet and registration tools with the FastMCP server."""

    mcp.tool(name="rancher_fleet_workspaces_list", annotations=READ_ONLY)(
        rancher_fleet_workspaces_list_tool
    )
    mcp.tool(name="rancher_fleet_workspace_get", annotations=READ_ONLY)(
        rancher_fleet_workspace_get_tool
    )
    mcp.tool(name="rancher_cluster_registration_tokens_list", annotations=READ_ONLY)(
        rancher_cluster_registration_tokens_list_tool
    )
    mcp.tool(name="rancher_cluster_registration_token_get", annotations=READ_ONLY)(
        rancher_cluster_registration_token_get_tool
    )
