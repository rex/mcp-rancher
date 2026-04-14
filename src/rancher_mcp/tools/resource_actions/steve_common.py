"""Shared Steve resource-loading helpers for generic action/link tools."""

from rancher_mcp.services.resources.contexts import (
    ResourceContext as SteveResourceContext,
)
from rancher_mcp.services.resources.contexts import (
    load_steve_resource_context,
)

__all__ = ["SteveResourceContext", "load_steve_resource_context"]
