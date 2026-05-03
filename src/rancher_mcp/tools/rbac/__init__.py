"""Curated Rancher RBAC tool facade."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.rbac.cluster_role_template_bindings import (
    rancher_cluster_role_template_binding_get,
    rancher_cluster_role_template_binding_get_tool,
    rancher_cluster_role_template_bindings_list,
    rancher_cluster_role_template_bindings_list_tool,
)
from rancher_mcp.tools.rbac.global_role_bindings import (
    rancher_global_role_binding_get,
    rancher_global_role_binding_get_tool,
    rancher_global_role_bindings_list,
    rancher_global_role_bindings_list_tool,
)
from rancher_mcp.tools.rbac.global_roles import (
    rancher_global_role_get,
    rancher_global_role_get_tool,
    rancher_global_roles_list,
    rancher_global_roles_list_tool,
)
from rancher_mcp.tools.rbac.project_role_template_bindings import (
    rancher_project_role_template_binding_get,
    rancher_project_role_template_binding_get_tool,
    rancher_project_role_template_bindings_list,
    rancher_project_role_template_bindings_list_tool,
)
from rancher_mcp.tools.rbac.role_templates import (
    rancher_role_template_get,
    rancher_role_template_get_tool,
    rancher_role_templates_list,
    rancher_role_templates_list_tool,
)
from rancher_mcp.tools.support.annotations import READ_ONLY

__all__ = [
    "rancher_cluster_role_template_binding_get",
    "rancher_cluster_role_template_bindings_list",
    "rancher_global_role_binding_get",
    "rancher_global_role_bindings_list",
    "rancher_global_role_get",
    "rancher_global_roles_list",
    "rancher_project_role_template_binding_get",
    "rancher_project_role_template_bindings_list",
    "rancher_role_template_get",
    "rancher_role_templates_list",
    "register_rbac_tools",
]


def register_rbac_tools(mcp: FastMCP) -> None:
    """Register curated RBAC tools with the FastMCP server."""

    mcp.tool(name="rancher_global_roles_list", annotations=READ_ONLY)(
        rancher_global_roles_list_tool
    )
    mcp.tool(name="rancher_global_role_get", annotations=READ_ONLY)(rancher_global_role_get_tool)
    mcp.tool(name="rancher_role_templates_list", annotations=READ_ONLY)(
        rancher_role_templates_list_tool
    )
    mcp.tool(name="rancher_role_template_get", annotations=READ_ONLY)(
        rancher_role_template_get_tool
    )
    mcp.tool(name="rancher_global_role_bindings_list", annotations=READ_ONLY)(
        rancher_global_role_bindings_list_tool
    )
    mcp.tool(name="rancher_global_role_binding_get", annotations=READ_ONLY)(
        rancher_global_role_binding_get_tool
    )
    mcp.tool(name="rancher_cluster_role_template_bindings_list", annotations=READ_ONLY)(
        rancher_cluster_role_template_bindings_list_tool
    )
    mcp.tool(name="rancher_cluster_role_template_binding_get", annotations=READ_ONLY)(
        rancher_cluster_role_template_binding_get_tool
    )
    mcp.tool(name="rancher_project_role_template_bindings_list", annotations=READ_ONLY)(
        rancher_project_role_template_bindings_list_tool
    )
    mcp.tool(name="rancher_project_role_template_binding_get", annotations=READ_ONLY)(
        rancher_project_role_template_binding_get_tool
    )
