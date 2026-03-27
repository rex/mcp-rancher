"""FastMCP server construction."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.discovery import register_discovery_tools
from rancher_mcp.tools.resources import register_resource_tools
from rancher_mcp.tools.settings_features import register_settings_feature_tools


def create_mcp_server() -> FastMCP:
    """Create and register the FastMCP server."""

    mcp = FastMCP(
        name="rancher-mcp",
        instructions="Capability-aware Rancher MCP server for Rancher 2.6.5",
    )
    register_discovery_tools(mcp)
    register_resource_tools(mcp)
    register_settings_feature_tools(mcp)
    return mcp


mcp = create_mcp_server()
