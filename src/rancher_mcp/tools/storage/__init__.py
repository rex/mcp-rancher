"""Curated Rancher storage tools."""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.storage.persistent_volume_claims import (
    rancher_persistent_volume_claim_get,
    rancher_persistent_volume_claim_get_tool,
    rancher_persistent_volume_claims_list,
    rancher_persistent_volume_claims_list_tool,
)
from rancher_mcp.tools.storage.persistent_volumes import (
    rancher_persistent_volume_get,
    rancher_persistent_volume_get_tool,
    rancher_persistent_volumes_list,
    rancher_persistent_volumes_list_tool,
)
from rancher_mcp.tools.storage.storage_classes import (
    rancher_storage_class_get,
    rancher_storage_class_get_tool,
    rancher_storage_classes_list,
    rancher_storage_classes_list_tool,
)
from rancher_mcp.tools.support.annotations import READ_ONLY

__all__ = [
    "rancher_persistent_volume_claim_get",
    "rancher_persistent_volume_claims_list",
    "rancher_persistent_volume_get",
    "rancher_persistent_volumes_list",
    "rancher_storage_class_get",
    "rancher_storage_classes_list",
    "register_storage_tools",
]


def register_storage_tools(mcp: FastMCP) -> None:
    """Register curated storage tools with the FastMCP server."""

    mcp.tool(name="rancher_storage_classes_list", annotations=READ_ONLY)(
        rancher_storage_classes_list_tool
    )
    mcp.tool(name="rancher_storage_class_get", annotations=READ_ONLY)(
        rancher_storage_class_get_tool
    )
    mcp.tool(name="rancher_persistent_volumes_list", annotations=READ_ONLY)(
        rancher_persistent_volumes_list_tool
    )
    mcp.tool(name="rancher_persistent_volume_get", annotations=READ_ONLY)(
        rancher_persistent_volume_get_tool
    )
    mcp.tool(name="rancher_persistent_volume_claims_list", annotations=READ_ONLY)(
        rancher_persistent_volume_claims_list_tool
    )
    mcp.tool(name="rancher_persistent_volume_claim_get", annotations=READ_ONLY)(
        rancher_persistent_volume_claim_get_tool
    )
