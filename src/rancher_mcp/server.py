"""FastMCP server construction."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register_all_tools(mcp: FastMCP) -> None:
    """Import and register every tool module on *mcp*.

    All tool-module imports are deferred until this function is called so that
    ``import rancher_mcp.server`` is cheap.  In production ``__main__.main()``
    calls this from a background thread, allowing the MCP ``initialize``
    handshake to complete before the heavy imports begin.
    """
    # Local imports are intentional: keep module-level import cost near-zero.
    from rancher_mcp.metrics import apply_metrics_to_all_tools
    from rancher_mcp.tools.alerts import register_alerts_tools
    from rancher_mcp.tools.apps_catalogs import register_app_catalog_tools
    from rancher_mcp.tools.auth_identity import register_auth_identity_tools
    from rancher_mcp.tools.backup_operator import register_backup_operator_tools
    from rancher_mcp.tools.batch_workloads import register_batch_workloads_tools
    from rancher_mcp.tools.cert_manager import register_cert_manager_tools
    from rancher_mcp.tools.certificates import register_certificates_tools
    from rancher_mcp.tools.clusters_nodes import register_cluster_node_tools
    from rancher_mcp.tools.compliance import register_compliance_tools
    from rancher_mcp.tools.config_secrets import register_config_secrets_tools
    from rancher_mcp.tools.discovery import register_discovery_tools
    from rancher_mcp.tools.disruption import register_disruption_tools
    from rancher_mcp.tools.fleet_registration import register_fleet_registration_tools
    from rancher_mcp.tools.governance import register_governance_tools
    from rancher_mcp.tools.logging_backups import register_logging_backup_tools
    from rancher_mcp.tools.logging_pipeline import register_logging_pipeline_tools
    from rancher_mcp.tools.longhorn import register_longhorn_tools
    from rancher_mcp.tools.mcp_prompts import register_mcp_prompts
    from rancher_mcp.tools.mcp_resources import register_mcp_resources
    from rancher_mcp.tools.monitoring import register_monitoring_tools
    from rancher_mcp.tools.networking import register_networking_tools
    from rancher_mcp.tools.ops import register_ops_tools
    from rancher_mcp.tools.pods_services import register_pod_service_tools
    from rancher_mcp.tools.policy_reports import register_policy_reports_tools
    from rancher_mcp.tools.projects_namespaces import register_project_namespace_tools
    from rancher_mcp.tools.prometheus_monitoring import (
        register_prometheus_monitoring_tools,
    )
    from rancher_mcp.tools.provisioning import register_provisioning_tools
    from rancher_mcp.tools.rbac import register_rbac_tools
    from rancher_mcp.tools.resources import register_resource_tools
    from rancher_mcp.tools.scheduling import register_scheduling_tools
    from rancher_mcp.tools.settings_features import register_settings_feature_tools
    from rancher_mcp.tools.storage import register_storage_tools
    from rancher_mcp.tools.support.errors import apply_structured_errors_to_all_tools
    from rancher_mcp.tools.workloads import register_workload_tools

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
    register_alerts_tools(mcp)
    register_workload_tools(mcp)
    register_networking_tools(mcp)
    register_config_secrets_tools(mcp)
    register_provisioning_tools(mcp)
    register_certificates_tools(mcp)
    register_backup_operator_tools(mcp)
    register_logging_pipeline_tools(mcp)
    register_policy_reports_tools(mcp)
    register_longhorn_tools(mcp)
    register_prometheus_monitoring_tools(mcp)
    register_cert_manager_tools(mcp)
    register_batch_workloads_tools(mcp)
    register_governance_tools(mcp)
    register_scheduling_tools(mcp)
    register_mcp_resources(mcp)
    register_mcp_prompts(mcp)
    # Order: metrics is INNER so it sees the original RancherMCPError;
    # structured_errors is OUTER and translates that to ToolError at the
    # MCP boundary.
    apply_metrics_to_all_tools(mcp)
    apply_structured_errors_to_all_tools(mcp)


def create_mcp_server() -> FastMCP:
    """Create a fully-configured FastMCP server (tools eager-loaded).

    Intended for tests and one-off scripts.  Production startup uses
    ``register_all_tools`` from a background thread instead.
    """
    from rancher_mcp.config import get_settings

    settings = get_settings()
    mcp = FastMCP(
        name=settings.server_name,
        instructions=settings.server_instructions,
    )
    register_all_tools(mcp)
    return mcp
