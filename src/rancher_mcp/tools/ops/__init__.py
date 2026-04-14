"""Operational convenience tools — high-value aggregate helpers."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.ops.cluster_health import (
    rancher_cluster_health_check_tool,
    rancher_cluster_nodes_summary_tool,
    rancher_clusters_health_summary_tool,
)
from rancher_mcp.tools.ops.find_failing_pods import rancher_find_failing_pods_tool
from rancher_mcp.tools.ops.find_pdbs_blocking import rancher_find_pdbs_blocking_tool
from rancher_mcp.tools.ops.find_services_no_endpoints import (
    rancher_find_services_without_endpoints_tool,
)
from rancher_mcp.tools.ops.find_stalled_rollouts import rancher_find_stalled_rollouts_tool
from rancher_mcp.tools.ops.find_unbound_pvcs import rancher_find_unbound_pvcs_tool
from rancher_mcp.tools.ops.find_unready_nodes import rancher_find_unready_nodes_tool
from rancher_mcp.tools.ops.rollups import (
    rancher_namespace_workloads_summary_tool,
    rancher_project_health_summary_tool,
)


def register_ops_tools(mcp: FastMCP) -> None:
    """Register operational convenience tools with the FastMCP server."""

    mcp.tool(name="rancher_cluster_health_check")(rancher_cluster_health_check_tool)
    mcp.tool(name="rancher_clusters_health_summary")(rancher_clusters_health_summary_tool)
    mcp.tool(name="rancher_cluster_nodes_summary")(rancher_cluster_nodes_summary_tool)
    mcp.tool(name="rancher_find_failing_pods")(rancher_find_failing_pods_tool)
    mcp.tool(name="rancher_find_unready_nodes")(rancher_find_unready_nodes_tool)
    mcp.tool(name="rancher_find_stalled_rollouts")(rancher_find_stalled_rollouts_tool)
    mcp.tool(name="rancher_find_services_without_endpoints")(
        rancher_find_services_without_endpoints_tool
    )
    mcp.tool(name="rancher_find_unbound_pvcs")(rancher_find_unbound_pvcs_tool)
    mcp.tool(name="rancher_find_pdbs_blocking")(rancher_find_pdbs_blocking_tool)
    mcp.tool(name="rancher_namespace_workloads_summary")(rancher_namespace_workloads_summary_tool)
    mcp.tool(name="rancher_project_health_summary")(rancher_project_health_summary_tool)
