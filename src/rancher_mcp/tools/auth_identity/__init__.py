"""Curated auth and identity tool facade."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.auth_identity.auth_configs import (
    rancher_auth_config_get,
    rancher_auth_config_get_tool,
    rancher_auth_configs_list,
    rancher_auth_configs_list_tool,
)
from rancher_mcp.tools.auth_identity.groups import (
    rancher_group_get,
    rancher_group_get_tool,
    rancher_groups_list,
    rancher_groups_list_tool,
)
from rancher_mcp.tools.auth_identity.users import (
    rancher_user_get,
    rancher_user_get_tool,
    rancher_users_list,
    rancher_users_list_tool,
)
from rancher_mcp.tools.support.annotations import READ_ONLY

__all__ = [
    "rancher_auth_config_get",
    "rancher_auth_configs_list",
    "rancher_group_get",
    "rancher_groups_list",
    "rancher_user_get",
    "rancher_users_list",
    "register_auth_identity_tools",
]


def register_auth_identity_tools(mcp: FastMCP) -> None:
    """Register curated auth and identity tools with the FastMCP server."""

    mcp.tool(name="rancher_users_list", annotations=READ_ONLY)(rancher_users_list_tool)
    mcp.tool(name="rancher_user_get", annotations=READ_ONLY)(rancher_user_get_tool)
    mcp.tool(name="rancher_groups_list", annotations=READ_ONLY)(rancher_groups_list_tool)
    mcp.tool(name="rancher_group_get", annotations=READ_ONLY)(rancher_group_get_tool)
    mcp.tool(name="rancher_auth_configs_list", annotations=READ_ONLY)(
        rancher_auth_configs_list_tool
    )
    mcp.tool(name="rancher_auth_config_get", annotations=READ_ONLY)(rancher_auth_config_get_tool)
