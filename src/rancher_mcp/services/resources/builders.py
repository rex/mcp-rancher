"""Stable public exports for generic resource builders."""

from rancher_mcp.services.resources.builders_collection import (
    build_resource_detail_model,
    build_resource_list_model,
)
from rancher_mcp.services.resources.builders_item import build_resource_item
from rancher_mcp.services.resources.builders_results import (
    build_resource_action_result,
    build_resource_link_result,
)
from rancher_mcp.services.resources.builders_watch import (
    build_resource_watch_event,
    build_resource_watch_result,
)

__all__ = [
    "build_resource_action_result",
    "build_resource_detail_model",
    "build_resource_item",
    "build_resource_link_result",
    "build_resource_list_model",
    "build_resource_watch_event",
    "build_resource_watch_result",
]
