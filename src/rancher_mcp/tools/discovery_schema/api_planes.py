# pyright: reportPrivateUsage=false
"""API-plane discovery tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.discovery import APIPlaneList, APIPlaneSummary
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.discovery_schema.shared import _api_version_string, _mapping_keys


async def _fetch_api_plane_list(
    instance_name: str,
    management_client: ManagementDiscoveryClient,
    steve_client: SteveDiscoveryClient,
    cluster_id: str,
) -> APIPlaneList:
    """Fetch the available API planes for an instance."""

    norman_root = await management_client.get_json("/v3")
    steve_root = await steve_client.get_json("/")
    planes = [
        APIPlaneSummary(
            id="norman",
            name="Rancher Norman management API",
            root_path="/v3",
            api_version=_api_version_string(norman_root.get("apiVersion")),
            link_count=len(_mapping_keys(norman_root.get("links"))),
        ),
        APIPlaneSummary(
            id="steve",
            name="Rancher Steve Kubernetes proxy API",
            root_path="/v1" if cluster_id == "local" else f"/k8s/clusters/{cluster_id}/v1",
            api_version=_api_version_string(steve_root.get("apiVersion")),
            cluster_id=cluster_id,
            link_count=len(_mapping_keys(steve_root.get("links"))),
        ),
    ]
    return APIPlaneList(instance=instance_name, cluster_id=cluster_id, planes=planes)


async def rancher_api_plane_list(
    instance: str | None = None,
    cluster_id: str = "local",
    settings: AppSettings | None = None,
    management_client: ManagementDiscoveryClient | None = None,
    steve_client: SteveDiscoveryClient | None = None,
) -> APIPlaneList:
    """List available Rancher API planes for an instance."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if management_client is not None and steve_client is not None:
        return await _fetch_api_plane_list(
            instance_name,
            management_client,
            steve_client,
            cluster_id,
        )
    async with (
        RancherManagementClient(instance_name, instance_config) as norman_client,
        RancherSteveClient(
            instance_name,
            instance_config,
            cluster_id=cluster_id,
        ) as proxy_client,
    ):
        return await _fetch_api_plane_list(
            instance_name,
            norman_client,
            proxy_client,
            cluster_id,
        )


async def rancher_api_plane_list_tool(
    instance: str | None = None,
    cluster_id: str = "local",
) -> APIPlaneList:
    """Public MCP wrapper for Rancher API plane discovery."""

    return await rancher_api_plane_list(instance=instance, cluster_id=cluster_id)
