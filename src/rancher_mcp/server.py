"""FastMCP server construction."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.apps_catalogs import register_app_catalog_tools
from rancher_mcp.tools.auth_identity import register_auth_identity_tools
from rancher_mcp.tools.clusters_nodes import register_cluster_node_tools
from rancher_mcp.tools.compliance import register_compliance_tools
from rancher_mcp.tools.discovery import register_discovery_tools
from rancher_mcp.tools.disruption import register_disruption_tools
from rancher_mcp.tools.fleet_registration import register_fleet_registration_tools
from rancher_mcp.tools.logging_backups import register_logging_backup_tools
from rancher_mcp.tools.monitoring import register_monitoring_tools
from rancher_mcp.tools.ops import register_ops_tools
from rancher_mcp.tools.pods_services import register_pod_service_tools
from rancher_mcp.tools.projects_namespaces import register_project_namespace_tools
from rancher_mcp.tools.rbac import register_rbac_tools
from rancher_mcp.tools.resources import register_resource_tools
from rancher_mcp.tools.settings_features import register_settings_feature_tools
from rancher_mcp.tools.storage import register_storage_tools
from rancher_mcp.tools.workloads import register_workload_tools


def create_mcp_server() -> FastMCP:
    """Create and register the FastMCP server."""

    mcp = FastMCP(
        name="rancher-mcp",
        instructions="Capability-aware Rancher MCP server for Rancher 2.6.5",
    )
    register_discovery_tools(mcp)
    register_disruption_tools(mcp)
    register_fleet_registration_tools(mcp)
    register_logging_backup_tools(mcp)
    register_ops_tools(mcp)
    register_resource_tools(mcp)
    register_cluster_node_tools(mcp)
    register_pod_service_tools(mcp)
    register_project_namespace_tools(mcp)
    register_app_catalog_tools(mcp)
    register_auth_identity_tools(mcp)
    register_rbac_tools(mcp)
    register_settings_feature_tools(mcp)
    register_storage_tools(mcp)
    register_monitoring_tools(mcp)
    register_compliance_tools(mcp)
    register_workload_tools(mcp)
    return mcp


mcp = create_mcp_server()
