"""Generic resource action/link tool facade."""

from rancher_mcp.tools.resource_actions.norman import (
    rancher_norman_resource_action_invoke,
    rancher_norman_resource_action_invoke_tool,
    rancher_norman_resource_link_follow,
    rancher_norman_resource_link_follow_tool,
)
from rancher_mcp.tools.resource_actions.steve import (
    rancher_steve_resource_action_invoke,
    rancher_steve_resource_action_invoke_tool,
    rancher_steve_resource_link_follow,
    rancher_steve_resource_link_follow_tool,
)

__all__ = [
    "rancher_norman_resource_action_invoke",
    "rancher_norman_resource_action_invoke_tool",
    "rancher_norman_resource_link_follow",
    "rancher_norman_resource_link_follow_tool",
    "rancher_steve_resource_action_invoke",
    "rancher_steve_resource_action_invoke_tool",
    "rancher_steve_resource_link_follow",
    "rancher_steve_resource_link_follow_tool",
]
