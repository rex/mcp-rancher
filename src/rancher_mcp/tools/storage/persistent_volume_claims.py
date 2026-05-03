"""Curated Rancher persistent-volume-claim tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.storage import (
    RancherPersistentVolumeClaimDetail,
    RancherPersistentVolumeClaimList,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resources.builders_pagination import next_page_token_from_payload
from rancher_mcp.tools.storage.paths import (
    persistent_volume_claim_collection_path,
    persistent_volume_claim_resource_path,
)
from rancher_mcp.tools.storage.shared import (
    build_list_query_params,
    items,
    persistent_volume_claim_summary_from_payload,
)
from rancher_mcp.tools.support.values import mapping_value, string_dict


async def _fetch_persistent_volume_claims_list(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    phase: str | None,
    storage_class_name: str | None,
    limit: int | None,
    client: ManagementDiscoveryClient,
    page_token: str | None = None,
) -> RancherPersistentVolumeClaimList:
    """Fetch and normalize PVCs through Rancher's raw Kubernetes proxy."""

    query_params = build_list_query_params(limit=limit, continue_token=page_token)
    payload = await client.get_json(
        persistent_volume_claim_collection_path(cluster_id, namespace),
        params=query_params or None,
    )
    claims = [persistent_volume_claim_summary_from_payload(item) for item in items(payload)]
    if phase is not None:
        claims = [claim for claim in claims if claim.phase == phase]
    if storage_class_name is not None:
        claims = [claim for claim in claims if claim.storage_class_name == storage_class_name]
    return RancherPersistentVolumeClaimList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        claim_count=len(claims),
        next_page_token=next_page_token_from_payload(payload),
        applied_query_params=query_params,
        persistent_volume_claims=claims,
    )


async def rancher_persistent_volume_claims_list(
    namespace: str,
    cluster_id: str = "local",
    phase: str | None = None,
    storage_class_name: str | None = None,
    limit: int | None = None,
    page_token: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherPersistentVolumeClaimList:
    """List persistent volume claims in one namespace with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_persistent_volume_claims_list(
            instance_name,
            cluster_id,
            namespace,
            phase,
            storage_class_name,
            limit,
            client,
            page_token,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_persistent_volume_claims_list(
            instance_name,
            cluster_id,
            namespace,
            phase,
            storage_class_name,
            limit,
            managed_client,
            page_token,
        )


async def _fetch_persistent_volume_claim_get(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    claim_name: str,
    client: ManagementDiscoveryClient,
) -> RancherPersistentVolumeClaimDetail:
    """Fetch and normalize one persistent volume claim."""

    payload = await client.get_json(
        persistent_volume_claim_resource_path(cluster_id, namespace, claim_name)
    )
    summary = persistent_volume_claim_summary_from_payload(payload)
    metadata = mapping_value(payload, "metadata") or {}
    return RancherPersistentVolumeClaimDetail.model_validate(payload).model_copy(
        update={
            "id": summary.id,
            "annotation_keys": sorted(string_dict(mapping_value(metadata, "annotations") or {})),
            "payload": dict(payload),
        }
    )


async def rancher_persistent_volume_claim_get(
    namespace: str,
    claim_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherPersistentVolumeClaimDetail:
    """Fetch one persistent volume claim by namespace and name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_persistent_volume_claim_get(
            instance_name,
            cluster_id,
            namespace,
            claim_name,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_persistent_volume_claim_get(
            instance_name,
            cluster_id,
            namespace,
            claim_name,
            managed_client,
        )


async def rancher_persistent_volume_claims_list_tool(
    namespace: str,
    cluster_id: str = "local",
    phase: str | None = None,
    storage_class_name: str | None = None,
    limit: int | None = None,
    page_token: str | None = None,
    instance: str | None = None,
) -> RancherPersistentVolumeClaimList:
    """Public MCP wrapper for curated persistent-volume-claim list."""

    return await rancher_persistent_volume_claims_list(
        namespace=namespace,
        cluster_id=cluster_id,
        phase=phase,
        storage_class_name=storage_class_name,
        limit=limit,
        page_token=page_token,
        instance=instance,
    )


async def rancher_persistent_volume_claim_get_tool(
    namespace: str,
    claim_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherPersistentVolumeClaimDetail:
    """Public MCP wrapper for curated persistent-volume-claim detail."""

    return await rancher_persistent_volume_claim_get(
        namespace=namespace,
        claim_name=claim_name,
        cluster_id=cluster_id,
        instance=instance,
    )
