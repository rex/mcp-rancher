"""Collapsed generic resource-kind mutation tools.

Three tools replace the 118 per-resource-family generated
`set_labels`/`set_annotations`/`delete` tools (42 + 42 + 34 across every
curated resource pack) with one uniform `(resource_kind, name, cluster_id,
namespace)` signature each, dispatched through the generated kind registry
(`_generated_kinds.py`, built by `make codegen` from every
`catalog/curated_tools/*.yml` descriptor that sets `generic_kind`).
"""

from mcp.server.fastmcp import FastMCP

from rancher_mcp.tools.resource_kinds.delete import (
    rancher_resource_delete,
    rancher_resource_delete_tool,
)
from rancher_mcp.tools.resource_kinds.metadata import (
    rancher_resource_set_annotations,
    rancher_resource_set_annotations_tool,
    rancher_resource_set_labels,
    rancher_resource_set_labels_tool,
)
from rancher_mcp.tools.support.annotations import DESTRUCTIVE, IDEMPOTENT_WRITE

__all__ = [
    "rancher_resource_delete",
    "rancher_resource_set_annotations",
    "rancher_resource_set_labels",
    "register_resource_kind_tools",
]


def register_resource_kind_tools(mcp: FastMCP) -> None:
    """Register the three collapsed generic resource-kind tools."""

    mcp.tool(name="rancher_resource_set_labels", annotations=IDEMPOTENT_WRITE)(
        rancher_resource_set_labels_tool
    )
    mcp.tool(name="rancher_resource_set_annotations", annotations=IDEMPOTENT_WRITE)(
        rancher_resource_set_annotations_tool
    )
    mcp.tool(name="rancher_resource_delete", annotations=DESTRUCTIVE)(rancher_resource_delete_tool)
