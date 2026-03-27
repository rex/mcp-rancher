"""FastMCP server construction."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.discovery import register_discovery_tools


def create_mcp_server() -> FastMCP:
    """Create and register the FastMCP server."""

    mcp = FastMCP(
        name="rancher-mcp",
        instructions="Capability-aware Rancher MCP server for Rancher 2.6.5",
    )
    register_discovery_tools(mcp)
    return mcp


mcp = create_mcp_server()
