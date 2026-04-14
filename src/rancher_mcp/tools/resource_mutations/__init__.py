"""Generic resource mutation tool facade."""

from rancher_mcp.tools.resource_mutations.norman_apply import (
    rancher_norman_resource_apply,
    rancher_norman_resource_apply_tool,
)
from rancher_mcp.tools.resource_mutations.norman_create import (
    rancher_norman_resource_create,
    rancher_norman_resource_create_tool,
)
from rancher_mcp.tools.resource_mutations.norman_delete import (
    rancher_norman_resource_delete,
    rancher_norman_resource_delete_tool,
)
from rancher_mcp.tools.resource_mutations.norman_patch import (
    rancher_norman_resource_patch,
    rancher_norman_resource_patch_tool,
)
from rancher_mcp.tools.resource_mutations.steve_apply import (
    rancher_steve_resource_apply,
    rancher_steve_resource_apply_tool,
)
from rancher_mcp.tools.resource_mutations.steve_create import (
    rancher_steve_resource_create,
    rancher_steve_resource_create_tool,
)
from rancher_mcp.tools.resource_mutations.steve_delete import (
    rancher_steve_resource_delete,
    rancher_steve_resource_delete_tool,
)
from rancher_mcp.tools.resource_mutations.steve_patch import (
    rancher_steve_resource_patch,
    rancher_steve_resource_patch_tool,
)

__all__ = [
    "rancher_norman_resource_apply",
    "rancher_norman_resource_apply_tool",
    "rancher_norman_resource_create",
    "rancher_norman_resource_create_tool",
    "rancher_norman_resource_delete",
    "rancher_norman_resource_delete_tool",
    "rancher_norman_resource_patch",
    "rancher_norman_resource_patch_tool",
    "rancher_steve_resource_apply",
    "rancher_steve_resource_apply_tool",
    "rancher_steve_resource_create",
    "rancher_steve_resource_create_tool",
    "rancher_steve_resource_delete",
    "rancher_steve_resource_delete_tool",
    "rancher_steve_resource_patch",
    "rancher_steve_resource_patch_tool",
]
