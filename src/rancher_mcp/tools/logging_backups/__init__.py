"""Curated Rancher logging and backup tool facade."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.logging_backups.cluster_loggings import (
    rancher_cluster_logging_get,
    rancher_cluster_logging_get_tool,
    rancher_cluster_loggings_list,
    rancher_cluster_loggings_list_tool,
)
from rancher_mcp.tools.logging_backups.etcd_backups import (
    rancher_etcd_backup_get,
    rancher_etcd_backup_get_tool,
    rancher_etcd_backups_list,
    rancher_etcd_backups_list_tool,
)
from rancher_mcp.tools.logging_backups.project_loggings import (
    rancher_project_logging_get,
    rancher_project_logging_get_tool,
    rancher_project_loggings_list,
    rancher_project_loggings_list_tool,
)

__all__ = [
    "rancher_cluster_logging_get",
    "rancher_cluster_loggings_list",
    "rancher_etcd_backup_get",
    "rancher_etcd_backups_list",
    "rancher_project_logging_get",
    "rancher_project_loggings_list",
    "register_logging_backup_tools",
]


def register_logging_backup_tools(mcp: FastMCP) -> None:
    """Register curated logging and backup tools with the FastMCP server."""

    mcp.tool(name="rancher_cluster_loggings_list")(rancher_cluster_loggings_list_tool)
    mcp.tool(name="rancher_cluster_logging_get")(rancher_cluster_logging_get_tool)
    mcp.tool(name="rancher_project_loggings_list")(rancher_project_loggings_list_tool)
    mcp.tool(name="rancher_project_logging_get")(rancher_project_logging_get_tool)
    mcp.tool(name="rancher_etcd_backups_list")(rancher_etcd_backups_list_tool)
    mcp.tool(name="rancher_etcd_backup_get")(rancher_etcd_backup_get_tool)
