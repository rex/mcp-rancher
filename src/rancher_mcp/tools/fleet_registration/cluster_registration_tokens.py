"""Curated Rancher cluster-registration-token tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.fleet_registration import (
    RancherClusterRegistrationTokenDetail,
    RancherClusterRegistrationTokenList,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.fleet_registration.shared import (
    action_keys,
    build_query_params,
    cluster_registration_token_summary_from_payload,
    data_items,
    link_keys,
)


async def _fetch_cluster_registration_tokens_list(
    instance_name: str,
    limit: int | None,
    cluster_id: str | None,
    name: str | None,
    state: str | None,
    namespace_id: str | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherClusterRegistrationTokenList:
    """Fetch and normalize the Rancher cluster-registration-token collection."""

    query_params = build_query_params(
        limit=limit,
        clusterId=cluster_id,
        name=name,
        state=state,
        namespaceId=namespace_id,
        sort=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/clusterregistrationtokens", params=query_params or None)
    tokens = [cluster_registration_token_summary_from_payload(item) for item in data_items(payload)]
    return RancherClusterRegistrationTokenList(
        instance=instance_name,
        cluster_registration_token_count=len(tokens),
        applied_query_params=query_params,
        cluster_registration_tokens=tokens,
    )


async def rancher_cluster_registration_tokens_list(
    limit: int | None = None,
    cluster_id: str | None = None,
    name: str | None = None,
    state: str | None = None,
    namespace_id: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherClusterRegistrationTokenList:
    """List Rancher cluster registration tokens with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cluster_registration_tokens_list(
            instance_name,
            limit,
            cluster_id,
            name,
            state,
            namespace_id,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cluster_registration_tokens_list(
            instance_name,
            limit,
            cluster_id,
            name,
            state,
            namespace_id,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_cluster_registration_token_get(
    cluster_registration_token_id: str,
    client: ManagementDiscoveryClient,
) -> RancherClusterRegistrationTokenDetail:
    """Fetch and normalize one Rancher cluster registration token."""

    payload = await client.get_json(
        f"/v3/clusterregistrationtokens/{cluster_registration_token_id}"
    )
    return RancherClusterRegistrationTokenDetail.model_validate(payload).model_copy(
        update={
            "action_keys": action_keys(payload),
            "link_keys": link_keys(payload),
            "payload": dict(payload),
        }
    )


async def rancher_cluster_registration_token_get(
    cluster_registration_token_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherClusterRegistrationTokenDetail:
    """Fetch one Rancher cluster registration token by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cluster_registration_token_get(cluster_registration_token_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cluster_registration_token_get(
            cluster_registration_token_id,
            managed_client,
        )


async def rancher_cluster_registration_tokens_list_tool(
    limit: int | None = None,
    cluster_id: str | None = None,
    name: str | None = None,
    state: str | None = None,
    namespace_id: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherClusterRegistrationTokenList:
    """Public MCP wrapper for curated cluster-registration-token list."""

    return await rancher_cluster_registration_tokens_list(
        limit=limit,
        cluster_id=cluster_id,
        name=name,
        state=state,
        namespace_id=namespace_id,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_cluster_registration_token_get_tool(
    cluster_registration_token_id: str,
    instance: str | None = None,
) -> RancherClusterRegistrationTokenDetail:
    """Public MCP wrapper for curated cluster-registration-token detail."""

    return await rancher_cluster_registration_token_get(
        cluster_registration_token_id=cluster_registration_token_id,
        instance=instance,
    )
