"""Thin facade for discovery tool registration and stable imports."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.discovery_catalog import (
    rancher_capability_domain_list,
    rancher_instance_list,
    rancher_server_profile_get,
)
from rancher_mcp.tools.discovery_schema import (
    rancher_api_plane_list,
    rancher_api_plane_list_tool,
    rancher_norman_schema_get,
    rancher_norman_schema_get_tool,
    rancher_norman_schema_list,
    rancher_norman_schema_list_tool,
    rancher_steve_schema_get,
    rancher_steve_schema_get_tool,
    rancher_steve_schema_list,
    rancher_steve_schema_list_tool,
)
from rancher_mcp.tools.discovery_server import (
    rancher_server_health,
    rancher_server_health_tool,
    rancher_server_version,
    rancher_server_version_tool,
)

__all__ = [
    "rancher_api_plane_list",
    "rancher_capability_domain_list",
    "rancher_instance_list",
    "rancher_norman_schema_get",
    "rancher_norman_schema_list",
    "rancher_server_health",
    "rancher_server_profile_get",
    "rancher_server_version",
    "rancher_steve_schema_get",
    "rancher_steve_schema_list",
    "register_discovery_tools",
]


def register_discovery_tools(mcp: FastMCP) -> None:
    """Register discovery tools with the FastMCP server."""

    mcp.tool(name="rancher_instance_list")(rancher_instance_list)
    mcp.tool(name="rancher_capability_domain_list")(rancher_capability_domain_list)
    mcp.tool(name="rancher_server_profile_get")(rancher_server_profile_get)
    mcp.tool(name="rancher_server_health")(rancher_server_health_tool)
    mcp.tool(name="rancher_server_version")(rancher_server_version_tool)
    mcp.tool(name="rancher_api_plane_list")(rancher_api_plane_list_tool)
    mcp.tool(name="rancher_norman_schema_list")(rancher_norman_schema_list_tool)
    mcp.tool(name="rancher_norman_schema_get")(rancher_norman_schema_get_tool)
    mcp.tool(name="rancher_steve_schema_list")(rancher_steve_schema_list_tool)
    mcp.tool(name="rancher_steve_schema_get")(rancher_steve_schema_get_tool)
