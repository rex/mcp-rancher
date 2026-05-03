"""MCP Resource registrations — rancher:// URI scheme."""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from rancher_mcp.config import get_settings
from rancher_mcp.services.catalog import get_capability_catalog
from rancher_mcp.services.instances import build_instance_list


async def _capabilities_resource() -> str:
    settings = get_settings()
    return Path(settings.catalog_path).read_text()


async def _instances_resource() -> str:
    settings = get_settings()
    catalog = get_capability_catalog(settings.catalog_path)
    instance_list = build_instance_list(settings, catalog.primary_target.version)
    return json.dumps(instance_list.model_dump(mode="json"), indent=2)


def register_mcp_resources(mcp: FastMCP) -> None:
    """Register rancher:// MCP resources with the server."""

    # FastMCP treats all rancher:// URIs as the same template pattern, so a
    # single template handler with internal dispatch is required.
    @mcp.resource(
        "rancher://{resource_id}",
        name="Rancher Resource",
        description=(
            "rancher://capabilities — YAML capability catalog. "
            "rancher://instances — JSON instance inventory."
        ),
        mime_type="application/json",
    )
    async def _rancher_resource(resource_id: str) -> str:  # pyright: ignore[reportUnusedFunction]
        if resource_id == "capabilities":
            return await _capabilities_resource()
        if resource_id == "instances":
            return await _instances_resource()
        raise ValueError(f"Unknown Rancher resource: {resource_id}")
