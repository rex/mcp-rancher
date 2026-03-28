"""Curated Rancher project and namespace tools."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.projects_namespaces.namespaces import (
    rancher_namespace_get,
    rancher_namespace_get_tool,
    rancher_namespaces_list,
    rancher_namespaces_list_tool,
)
from rancher_mcp.tools.projects_namespaces.projects import (
    rancher_project_get,
    rancher_project_get_tool,
    rancher_projects_list,
    rancher_projects_list_tool,
)

__all__ = [
    "rancher_namespace_get",
    "rancher_namespaces_list",
    "rancher_project_get",
    "rancher_projects_list",
    "register_project_namespace_tools",
]


def register_project_namespace_tools(mcp: FastMCP) -> None:
    """Register curated project/namespace tools with the FastMCP server."""

    mcp.tool(name="rancher_projects_list")(rancher_projects_list_tool)
    mcp.tool(name="rancher_project_get")(rancher_project_get_tool)
    mcp.tool(name="rancher_namespaces_list")(rancher_namespaces_list_tool)
    mcp.tool(name="rancher_namespace_get")(rancher_namespace_get_tool)
