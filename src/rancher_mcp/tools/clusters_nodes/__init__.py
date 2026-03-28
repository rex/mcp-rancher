"""Curated Rancher cluster and node tools."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.clusters_nodes.clusters import (
    rancher_cluster_get,
    rancher_cluster_get_tool,
    rancher_clusters_list,
    rancher_clusters_list_tool,
)
from rancher_mcp.tools.clusters_nodes.nodes import (
    rancher_node_get,
    rancher_node_get_tool,
    rancher_nodes_list,
    rancher_nodes_list_tool,
)

__all__ = [
    "rancher_cluster_get",
    "rancher_clusters_list",
    "rancher_node_get",
    "rancher_nodes_list",
    "register_cluster_node_tools",
]


def register_cluster_node_tools(mcp: FastMCP) -> None:
    """Register curated cluster/node tools with the FastMCP server."""

    mcp.tool(name="rancher_clusters_list")(rancher_clusters_list_tool)
    mcp.tool(name="rancher_cluster_get")(rancher_cluster_get_tool)
    mcp.tool(name="rancher_nodes_list")(rancher_nodes_list_tool)
    mcp.tool(name="rancher_node_get")(rancher_node_get_tool)
