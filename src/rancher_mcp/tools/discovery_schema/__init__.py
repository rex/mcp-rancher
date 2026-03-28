"""API-plane and schema discovery tool facade."""

from rancher_mcp.tools.discovery_schema.api_planes import (
    rancher_api_plane_list,
    rancher_api_plane_list_tool,
)
from rancher_mcp.tools.discovery_schema.norman import (
    rancher_norman_schema_get,
    rancher_norman_schema_get_tool,
    rancher_norman_schema_list,
    rancher_norman_schema_list_tool,
)
from rancher_mcp.tools.discovery_schema.steve import (
    rancher_steve_schema_get,
    rancher_steve_schema_get_tool,
    rancher_steve_schema_list,
    rancher_steve_schema_list_tool,
)

__all__ = [
    "rancher_api_plane_list",
    "rancher_api_plane_list_tool",
    "rancher_norman_schema_get",
    "rancher_norman_schema_get_tool",
    "rancher_norman_schema_list",
    "rancher_norman_schema_list_tool",
    "rancher_steve_schema_get",
    "rancher_steve_schema_get_tool",
    "rancher_steve_schema_list",
    "rancher_steve_schema_list_tool",
]
