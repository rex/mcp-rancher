"""Curated Rancher pod and service tools."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.pods_services.pods import (
    rancher_pod_get,
    rancher_pod_get_tool,
    rancher_pods_list,
    rancher_pods_list_tool,
)
from rancher_mcp.tools.pods_services.services import (
    rancher_service_get,
    rancher_service_get_tool,
    rancher_services_list,
    rancher_services_list_tool,
)

__all__ = [
    "rancher_pod_get",
    "rancher_pods_list",
    "rancher_service_get",
    "rancher_services_list",
    "register_pod_service_tools",
]


def register_pod_service_tools(mcp: FastMCP) -> None:
    """Register curated pod/service tools with the FastMCP server."""

    mcp.tool(name="rancher_pods_list")(rancher_pods_list_tool)
    mcp.tool(name="rancher_pod_get")(rancher_pod_get_tool)
    mcp.tool(name="rancher_services_list")(rancher_services_list_tool)
    mcp.tool(name="rancher_service_get")(rancher_service_get_tool)
