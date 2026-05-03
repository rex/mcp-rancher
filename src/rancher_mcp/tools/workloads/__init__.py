"""Curated Rancher workload-controller tools."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.support.annotations import READ_ONLY
from rancher_mcp.tools.workloads.daemonsets import (
    rancher_daemonset_get,
    rancher_daemonset_get_tool,
    rancher_daemonsets_list,
    rancher_daemonsets_list_tool,
)
from rancher_mcp.tools.workloads.deployments import (
    rancher_deployment_get,
    rancher_deployment_get_tool,
    rancher_deployments_list,
    rancher_deployments_list_tool,
)
from rancher_mcp.tools.workloads.statefulsets import (
    rancher_statefulset_get,
    rancher_statefulset_get_tool,
    rancher_statefulsets_list,
    rancher_statefulsets_list_tool,
)

__all__ = [
    "rancher_daemonset_get",
    "rancher_daemonsets_list",
    "rancher_deployment_get",
    "rancher_deployments_list",
    "rancher_statefulset_get",
    "rancher_statefulsets_list",
    "register_workload_tools",
]


def register_workload_tools(mcp: FastMCP) -> None:
    """Register curated workload-controller tools with the FastMCP server."""

    mcp.tool(name="rancher_deployments_list", annotations=READ_ONLY)(rancher_deployments_list_tool)
    mcp.tool(name="rancher_deployment_get", annotations=READ_ONLY)(rancher_deployment_get_tool)
    mcp.tool(name="rancher_daemonsets_list", annotations=READ_ONLY)(rancher_daemonsets_list_tool)
    mcp.tool(name="rancher_daemonset_get", annotations=READ_ONLY)(rancher_daemonset_get_tool)
    mcp.tool(name="rancher_statefulsets_list", annotations=READ_ONLY)(
        rancher_statefulsets_list_tool
    )
    mcp.tool(name="rancher_statefulset_get", annotations=READ_ONLY)(rancher_statefulset_get_tool)
