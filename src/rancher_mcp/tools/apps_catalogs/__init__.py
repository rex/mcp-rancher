"""Curated app catalog tool facade."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.apps_catalogs.catalogs import (
    rancher_catalog_get,
    rancher_catalog_get_tool,
    rancher_catalogs_list,
    rancher_catalogs_list_tool,
)
from rancher_mcp.tools.apps_catalogs.template_versions import (
    rancher_template_version_get,
    rancher_template_version_get_tool,
    rancher_template_versions_list,
    rancher_template_versions_list_tool,
)
from rancher_mcp.tools.apps_catalogs.templates import (
    rancher_template_get,
    rancher_template_get_tool,
    rancher_templates_list,
    rancher_templates_list_tool,
)
from rancher_mcp.tools.support.annotations import READ_ONLY

__all__ = [
    "rancher_catalog_get",
    "rancher_catalogs_list",
    "rancher_template_get",
    "rancher_template_version_get",
    "rancher_template_versions_list",
    "rancher_templates_list",
    "register_app_catalog_tools",
]


def register_app_catalog_tools(mcp: FastMCP) -> None:
    """Register curated app catalog tools with the FastMCP server."""

    mcp.tool(name="rancher_catalogs_list", annotations=READ_ONLY)(rancher_catalogs_list_tool)
    mcp.tool(name="rancher_catalog_get", annotations=READ_ONLY)(rancher_catalog_get_tool)
    mcp.tool(name="rancher_templates_list", annotations=READ_ONLY)(rancher_templates_list_tool)
    mcp.tool(name="rancher_template_get", annotations=READ_ONLY)(rancher_template_get_tool)
    mcp.tool(name="rancher_template_versions_list", annotations=READ_ONLY)(
        rancher_template_versions_list_tool
    )
    mcp.tool(name="rancher_template_version_get", annotations=READ_ONLY)(
        rancher_template_version_get_tool
    )
