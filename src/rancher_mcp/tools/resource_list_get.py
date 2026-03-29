"""Thin facade for generic resource list/get tools."""

from rancher_mcp.tools.resource_list_get_norman import (
    rancher_norman_resource_get,
    rancher_norman_resource_get_tool,
    rancher_norman_resource_list,
    rancher_norman_resource_list_tool,
)
from rancher_mcp.tools.resource_list_get_steve import (
    rancher_steve_resource_get,
    rancher_steve_resource_get_tool,
    rancher_steve_resource_list,
    rancher_steve_resource_list_tool,
)

__all__ = [
    "rancher_norman_resource_get",
    "rancher_norman_resource_get_tool",
    "rancher_norman_resource_list",
    "rancher_norman_resource_list_tool",
    "rancher_steve_resource_get",
    "rancher_steve_resource_get_tool",
    "rancher_steve_resource_list",
    "rancher_steve_resource_list_tool",
]
