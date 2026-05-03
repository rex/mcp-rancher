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

    mcp.resource(
        "rancher://capabilities",
        name="Rancher Capabilities",
        description=(
            "Machine-readable capability catalog — tool domains available "
            "and their compatibility with Rancher versions."
        ),
        mime_type="application/yaml",
    )(_capabilities_resource)

    mcp.resource(
        "rancher://instances",
        name="Rancher Instances",
        description=(
            "Configured Rancher instance inventory — names, URLs, "
            "read-only status, and default instance designation."
        ),
        mime_type="application/json",
    )(_instances_resource)
