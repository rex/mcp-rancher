"""Curated Rancher alerting and notifier tool facade."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.alerts.alert_rules import (
    rancher_cluster_alert_rule_get,
    rancher_cluster_alert_rule_get_tool,
    rancher_cluster_alert_rules_list,
    rancher_cluster_alert_rules_list_tool,
)
from rancher_mcp.tools.alerts.notifiers import (
    rancher_notifier_get,
    rancher_notifier_get_tool,
    rancher_notifiers_list,
    rancher_notifiers_list_tool,
)

__all__ = [
    "rancher_cluster_alert_rule_get",
    "rancher_cluster_alert_rules_list",
    "rancher_notifier_get",
    "rancher_notifiers_list",
    "register_alerts_tools",
]


def register_alerts_tools(mcp: FastMCP) -> None:
    """Register curated alerting and notifier tools with the FastMCP server."""

    mcp.tool(name="rancher_notifiers_list")(rancher_notifiers_list_tool)
    mcp.tool(name="rancher_notifier_get")(rancher_notifier_get_tool)
    mcp.tool(name="rancher_cluster_alert_rules_list")(rancher_cluster_alert_rules_list_tool)
    mcp.tool(name="rancher_cluster_alert_rule_get")(rancher_cluster_alert_rule_get_tool)
