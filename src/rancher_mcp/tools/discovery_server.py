"""Server health and version discovery tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.management import ServerHealth, ServerVersion
from rancher_mcp.services.instances import resolve_instance


async def _fetch_server_health(
    instance_name: str,
    client: ManagementDiscoveryClient,
) -> ServerHealth:
    """Fetch Rancher server health using an injected client."""

    message = (await client.get_text("/healthz")).strip() or None
    return ServerHealth(instance=instance_name, healthy=True, message=message)


async def rancher_server_health(
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> ServerHealth:
    """Check the Rancher management server health endpoint."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_server_health(instance_name, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_server_health(instance_name, managed_client)


async def _fetch_server_version(
    instance_name: str,
    client: ManagementDiscoveryClient,
) -> ServerVersion:
    """Fetch Rancher server version using an injected client."""

    payload = await client.get_json("/v3/settings/server-version")
    raw_value = payload.get("value")
    version = raw_value if isinstance(raw_value, str) else None
    return ServerVersion(instance=instance_name, rancher_version=version)


async def rancher_server_version(
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> ServerVersion:
    """Fetch Rancher server version."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_server_version(instance_name, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_server_version(instance_name, managed_client)


async def rancher_server_health_tool(instance: str | None = None) -> ServerHealth:
    """Public MCP wrapper for Rancher server health."""

    return await rancher_server_health(instance=instance)


async def rancher_server_version_tool(instance: str | None = None) -> ServerVersion:
    """Public MCP wrapper for Rancher server version."""

    return await rancher_server_version(instance=instance)
