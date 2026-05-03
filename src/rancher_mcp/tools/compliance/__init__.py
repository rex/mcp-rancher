"""Curated Rancher CIS compliance tool facade."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.compliance.cis_profiles import (
    rancher_cis_scan_profile_get,
    rancher_cis_scan_profile_get_tool,
    rancher_cis_scan_profiles_list,
    rancher_cis_scan_profiles_list_tool,
)
from rancher_mcp.tools.compliance.cis_scans import (
    rancher_cis_scan_get,
    rancher_cis_scan_get_tool,
    rancher_cis_scans_list,
    rancher_cis_scans_list_tool,
)
from rancher_mcp.tools.support.annotations import READ_ONLY

__all__ = [
    "rancher_cis_scan_get",
    "rancher_cis_scan_profile_get",
    "rancher_cis_scan_profiles_list",
    "rancher_cis_scans_list",
    "register_compliance_tools",
]


def register_compliance_tools(mcp: FastMCP) -> None:
    """Register curated CIS compliance tools with the FastMCP server."""

    mcp.tool(name="rancher_cis_scan_profiles_list", annotations=READ_ONLY)(
        rancher_cis_scan_profiles_list_tool
    )
    mcp.tool(name="rancher_cis_scan_profile_get", annotations=READ_ONLY)(
        rancher_cis_scan_profile_get_tool
    )
    mcp.tool(name="rancher_cis_scans_list", annotations=READ_ONLY)(rancher_cis_scans_list_tool)
    mcp.tool(name="rancher_cis_scan_get", annotations=READ_ONLY)(rancher_cis_scan_get_tool)
