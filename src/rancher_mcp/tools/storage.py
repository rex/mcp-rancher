"""Curated Rancher storage read-only tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from urllib.parse import quote

from mcp.server.fastmcp import FastMCP

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.storage import (
    RancherPersistentVolumeClaimDetail,
    RancherPersistentVolumeClaimList,
    RancherPersistentVolumeClaimSummary,
    RancherPersistentVolumeDetail,
    RancherPersistentVolumeList,
    RancherPersistentVolumeSummary,
    RancherStorageClassDetail,
    RancherStorageClassList,
    RancherStorageClassSummary,
)
from rancher_mcp.services.instances import resolve_instance


async def _fetch_storage_classes_list(
    instance_name: str,
    cluster_id: str,
    default_only: bool | None,
    limit: int | None,
    client: ManagementDiscoveryClient,
) -> RancherStorageClassList:
    """Fetch and normalize storage classes through Rancher's raw Kubernetes proxy."""

    query_params = _build_list_query_params(limit=limit)
    payload = await client.get_json(
        _storage_class_collection_path(cluster_id),
        params=query_params or None,
    )
    storage_classes = [_storage_class_summary_from_payload(item) for item in _items(payload)]
    if default_only is True:
        storage_classes = [
            storage_class
            for storage_class in storage_classes
            if storage_class.default_class is True
        ]
    return RancherStorageClassList(
        instance=instance_name,
        cluster_id=cluster_id,
        storage_class_count=len(storage_classes),
        applied_query_params=query_params,
        storage_classes=storage_classes,
    )


async def rancher_storage_classes_list(
    cluster_id: str = "local",
    default_only: bool | None = None,
    limit: int | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherStorageClassList:
    """List storage classes with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_storage_classes_list(
            instance_name,
            cluster_id,
            default_only,
            limit,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_storage_classes_list(
            instance_name,
            cluster_id,
            default_only,
            limit,
            managed_client,
        )


async def _fetch_storage_class_get(
    instance_name: str,
    cluster_id: str,
    storage_class_name: str,
    client: ManagementDiscoveryClient,
) -> RancherStorageClassDetail:
    """Fetch and normalize one storage class."""

    payload = await client.get_json(_storage_class_resource_path(cluster_id, storage_class_name))
    summary = _storage_class_summary_from_payload(payload)
    metadata = _mapping_value(payload, "metadata") or {}
    return RancherStorageClassDetail(
        name=summary.name,
        provisioner=summary.provisioner,
        reclaim_policy=summary.reclaim_policy,
        volume_binding_mode=summary.volume_binding_mode,
        allow_volume_expansion=summary.allow_volume_expansion,
        default_class=summary.default_class,
        parameter_keys=summary.parameter_keys,
        mount_options=_string_list(payload.get("mountOptions")),
        annotation_keys=sorted(_string_dict(_mapping_value(metadata, "annotations") or {})),
        payload=dict(payload),
    )


async def rancher_storage_class_get(
    storage_class_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherStorageClassDetail:
    """Fetch one storage class by name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_storage_class_get(
            instance_name,
            cluster_id,
            storage_class_name,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_storage_class_get(
            instance_name,
            cluster_id,
            storage_class_name,
            managed_client,
        )


async def _fetch_persistent_volumes_list(
    instance_name: str,
    cluster_id: str,
    phase: str | None,
    storage_class_name: str | None,
    limit: int | None,
    client: ManagementDiscoveryClient,
) -> RancherPersistentVolumeList:
    """Fetch and normalize persistent volumes through Rancher's raw Kubernetes proxy."""

    query_params = _build_list_query_params(limit=limit)
    payload = await client.get_json(
        _persistent_volume_collection_path(cluster_id),
        params=query_params or None,
    )
    volumes = [_persistent_volume_summary_from_payload(item) for item in _items(payload)]
    if phase is not None:
        volumes = [volume for volume in volumes if volume.phase == phase]
    if storage_class_name is not None:
        volumes = [volume for volume in volumes if volume.storage_class_name == storage_class_name]
    return RancherPersistentVolumeList(
        instance=instance_name,
        cluster_id=cluster_id,
        volume_count=len(volumes),
        applied_query_params=query_params,
        persistent_volumes=volumes,
    )


async def rancher_persistent_volumes_list(
    cluster_id: str = "local",
    phase: str | None = None,
    storage_class_name: str | None = None,
    limit: int | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherPersistentVolumeList:
    """List persistent volumes with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_persistent_volumes_list(
            instance_name,
            cluster_id,
            phase,
            storage_class_name,
            limit,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_persistent_volumes_list(
            instance_name,
            cluster_id,
            phase,
            storage_class_name,
            limit,
            managed_client,
        )


async def _fetch_persistent_volume_get(
    instance_name: str,
    cluster_id: str,
    volume_name: str,
    client: ManagementDiscoveryClient,
) -> RancherPersistentVolumeDetail:
    """Fetch and normalize one persistent volume."""

    payload = await client.get_json(_persistent_volume_resource_path(cluster_id, volume_name))
    summary = _persistent_volume_summary_from_payload(payload)
    metadata = _mapping_value(payload, "metadata") or {}
    annotations = _mapping_value(metadata, "annotations") or {}
    return RancherPersistentVolumeDetail(
        name=summary.name,
        phase=summary.phase,
        storage_class_name=summary.storage_class_name,
        capacity_storage=summary.capacity_storage,
        claim_namespace=summary.claim_namespace,
        claim_name=summary.claim_name,
        reclaim_policy=summary.reclaim_policy,
        access_modes=summary.access_modes,
        volume_mode=summary.volume_mode,
        volume_source_type=summary.volume_source_type,
        finalizers=_string_list(metadata.get("finalizers")),
        node_hostnames=_persistent_volume_node_hostnames(payload),
        provisioner=_string_value(annotations, "pv.kubernetes.io/provisioned-by"),
        payload=dict(payload),
    )


async def rancher_persistent_volume_get(
    volume_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherPersistentVolumeDetail:
    """Fetch one persistent volume by name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_persistent_volume_get(
            instance_name,
            cluster_id,
            volume_name,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_persistent_volume_get(
            instance_name,
            cluster_id,
            volume_name,
            managed_client,
        )


async def _fetch_persistent_volume_claims_list(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    phase: str | None,
    storage_class_name: str | None,
    limit: int | None,
    client: ManagementDiscoveryClient,
) -> RancherPersistentVolumeClaimList:
    """Fetch and normalize PVCs through Rancher's raw Kubernetes proxy."""

    query_params = _build_list_query_params(limit=limit)
    payload = await client.get_json(
        _persistent_volume_claim_collection_path(cluster_id, namespace),
        params=query_params or None,
    )
    claims = [_persistent_volume_claim_summary_from_payload(item) for item in _items(payload)]
    if phase is not None:
        claims = [claim for claim in claims if claim.phase == phase]
    if storage_class_name is not None:
        claims = [claim for claim in claims if claim.storage_class_name == storage_class_name]
    return RancherPersistentVolumeClaimList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        claim_count=len(claims),
        applied_query_params=query_params,
        persistent_volume_claims=claims,
    )


async def rancher_persistent_volume_claims_list(
    namespace: str,
    cluster_id: str = "local",
    phase: str | None = None,
    storage_class_name: str | None = None,
    limit: int | None = None,
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
        _persistent_volume_claim_resource_path(cluster_id, namespace, claim_name)
    )
    summary = _persistent_volume_claim_summary_from_payload(payload)
    metadata = _mapping_value(payload, "metadata") or {}
    annotations = _mapping_value(metadata, "annotations") or {}
    return RancherPersistentVolumeClaimDetail(
        id=summary.id,
        name=summary.name,
        namespace=summary.namespace,
        phase=summary.phase,
        storage_class_name=summary.storage_class_name,
        requested_storage=summary.requested_storage,
        capacity_storage=summary.capacity_storage,
        volume_name=summary.volume_name,
        access_modes=summary.access_modes,
        volume_mode=summary.volume_mode,
        annotation_keys=sorted(_string_dict(annotations)),
        finalizers=_string_list(metadata.get("finalizers")),
        selected_node=_string_value(annotations, "volume.kubernetes.io/selected-node"),
        payload=dict(payload),
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


def register_storage_tools(mcp: FastMCP) -> None:
    """Register curated storage tools with the FastMCP server."""

    mcp.tool(name="rancher_storage_classes_list")(rancher_storage_classes_list_tool)
    mcp.tool(name="rancher_storage_class_get")(rancher_storage_class_get_tool)
    mcp.tool(name="rancher_persistent_volumes_list")(rancher_persistent_volumes_list_tool)
    mcp.tool(name="rancher_persistent_volume_get")(rancher_persistent_volume_get_tool)
    mcp.tool(name="rancher_persistent_volume_claims_list")(
        rancher_persistent_volume_claims_list_tool
    )
    mcp.tool(name="rancher_persistent_volume_claim_get")(rancher_persistent_volume_claim_get_tool)


async def rancher_storage_classes_list_tool(
    cluster_id: str = "local",
    default_only: bool | None = None,
    limit: int | None = None,
    instance: str | None = None,
) -> RancherStorageClassList:
    """Public MCP wrapper for curated storage-class list."""

    return await rancher_storage_classes_list(
        cluster_id=cluster_id,
        default_only=default_only,
        limit=limit,
        instance=instance,
    )


async def rancher_storage_class_get_tool(
    storage_class_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherStorageClassDetail:
    """Public MCP wrapper for curated storage-class detail."""

    return await rancher_storage_class_get(
        storage_class_name=storage_class_name,
        cluster_id=cluster_id,
        instance=instance,
    )


async def rancher_persistent_volumes_list_tool(
    cluster_id: str = "local",
    phase: str | None = None,
    storage_class_name: str | None = None,
    limit: int | None = None,
    instance: str | None = None,
) -> RancherPersistentVolumeList:
    """Public MCP wrapper for curated persistent-volume list."""

    return await rancher_persistent_volumes_list(
        cluster_id=cluster_id,
        phase=phase,
        storage_class_name=storage_class_name,
        limit=limit,
        instance=instance,
    )


async def rancher_persistent_volume_get_tool(
    volume_name: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherPersistentVolumeDetail:
    """Public MCP wrapper for curated persistent-volume detail."""

    return await rancher_persistent_volume_get(
        volume_name=volume_name,
        cluster_id=cluster_id,
        instance=instance,
    )


async def rancher_persistent_volume_claims_list_tool(
    namespace: str,
    cluster_id: str = "local",
    phase: str | None = None,
    storage_class_name: str | None = None,
    limit: int | None = None,
    instance: str | None = None,
) -> RancherPersistentVolumeClaimList:
    """Public MCP wrapper for curated persistent-volume-claim list."""

    return await rancher_persistent_volume_claims_list(
        namespace=namespace,
        cluster_id=cluster_id,
        phase=phase,
        storage_class_name=storage_class_name,
        limit=limit,
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


def _build_list_query_params(*, limit: int | None) -> dict[str, str | int | bool]:
    """Build typed list query params for raw Kubernetes proxy list calls."""

    if limit is None:
        return {}
    return {"limit": limit}


def _storage_class_collection_path(cluster_id: str) -> str:
    """Build the raw Kubernetes proxy collection path for storage classes."""

    return _group_collection_path(
        cluster_id=cluster_id,
        api_group="storage.k8s.io",
        api_version="v1",
        resource="storageclasses",
    )


def _storage_class_resource_path(cluster_id: str, storage_class_name: str) -> str:
    """Build the raw Kubernetes proxy resource path for one storage class."""

    return _append_identifier(_storage_class_collection_path(cluster_id), storage_class_name)


def _persistent_volume_collection_path(cluster_id: str) -> str:
    """Build the raw Kubernetes proxy collection path for persistent volumes."""

    return _core_collection_path(
        cluster_id=cluster_id,
        api_version="v1",
        resource="persistentvolumes",
    )


def _persistent_volume_resource_path(cluster_id: str, volume_name: str) -> str:
    """Build the raw Kubernetes proxy resource path for one persistent volume."""

    return _append_identifier(_persistent_volume_collection_path(cluster_id), volume_name)


def _persistent_volume_claim_collection_path(cluster_id: str, namespace: str) -> str:
    """Build the raw Kubernetes proxy collection path for PVCs in one namespace."""

    return _core_collection_path(
        cluster_id=cluster_id,
        api_version="v1",
        resource="persistentvolumeclaims",
        namespace=namespace,
    )


def _persistent_volume_claim_resource_path(
    cluster_id: str,
    namespace: str,
    claim_name: str,
) -> str:
    """Build the raw Kubernetes proxy resource path for one PVC."""

    return _append_identifier(
        _persistent_volume_claim_collection_path(cluster_id, namespace),
        claim_name,
    )


def _storage_class_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherStorageClassSummary:
    """Normalize one storage-class payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    annotations = _mapping_value(metadata, "annotations") or {}
    parameters = _mapping_value(payload, "parameters") or {}
    return RancherStorageClassSummary(
        name=_string_value(metadata, "name") or "<unknown-storage-class>",
        provisioner=_string_value(payload, "provisioner"),
        reclaim_policy=_string_value(payload, "reclaimPolicy"),
        volume_binding_mode=_string_value(payload, "volumeBindingMode"),
        allow_volume_expansion=_bool_value(payload, "allowVolumeExpansion"),
        default_class=_annotation_true(
            annotations,
            "storageclass.kubernetes.io/is-default-class",
        ),
        parameter_keys=sorted(_string_dict(parameters)),
    )


def _persistent_volume_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherPersistentVolumeSummary:
    """Normalize one persistent-volume payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    spec = _mapping_value(payload, "spec") or {}
    claim_ref = _mapping_value(spec, "claimRef") or {}
    return RancherPersistentVolumeSummary(
        name=_string_value(metadata, "name") or "<unknown-persistent-volume>",
        phase=_string_value(_mapping_value(payload, "status"), "phase"),
        storage_class_name=_string_value(spec, "storageClassName"),
        capacity_storage=_string_value(_mapping_value(spec, "capacity"), "storage"),
        claim_namespace=_string_value(claim_ref, "namespace"),
        claim_name=_string_value(claim_ref, "name"),
        reclaim_policy=_string_value(spec, "persistentVolumeReclaimPolicy"),
        access_modes=_string_list(spec.get("accessModes")),
        volume_mode=_string_value(spec, "volumeMode"),
        volume_source_type=_persistent_volume_source_type(spec),
    )


def _persistent_volume_claim_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherPersistentVolumeClaimSummary:
    """Normalize one persistent-volume-claim payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    spec = _mapping_value(payload, "spec") or {}
    status = _mapping_value(payload, "status") or {}
    name = _string_value(metadata, "name") or "<unknown-persistent-volume-claim>"
    namespace = _string_value(metadata, "namespace") or "<unknown-namespace>"
    return RancherPersistentVolumeClaimSummary(
        id=f"{namespace}/{name}",
        name=name,
        namespace=namespace,
        phase=_string_value(status, "phase"),
        storage_class_name=_string_value(spec, "storageClassName"),
        requested_storage=_string_value(
            _mapping_value(_mapping_value(spec, "resources"), "requests"),
            "storage",
        ),
        capacity_storage=_string_value(_mapping_value(status, "capacity"), "storage"),
        volume_name=_string_value(spec, "volumeName"),
        access_modes=_string_list(status.get("accessModes"))
        or _string_list(spec.get("accessModes")),
        volume_mode=_string_value(spec, "volumeMode"),
    )


def _persistent_volume_node_hostnames(payload: Mapping[str, object]) -> list[str]:
    """Extract bound node hostnames from a persistent volume's node affinity."""

    spec = _mapping_value(payload, "spec") or {}
    node_affinity = _mapping_value(spec, "nodeAffinity") or {}
    required = _mapping_value(node_affinity, "required") or {}
    raw_terms = required.get("nodeSelectorTerms")
    if not isinstance(raw_terms, list):
        return []
    hostnames: list[str] = []
    typed_terms = cast(list[object], raw_terms)
    for raw_term in typed_terms:
        if not isinstance(raw_term, dict):
            continue
        term = cast(dict[str, object], raw_term)
        raw_expressions = term.get("matchExpressions")
        if not isinstance(raw_expressions, list):
            continue
        typed_expressions = cast(list[object], raw_expressions)
        for raw_expression in typed_expressions:
            if not isinstance(raw_expression, dict):
                continue
            expression = cast(dict[str, object], raw_expression)
            if _string_value(expression, "key") != "kubernetes.io/hostname":
                continue
            hostnames.extend(_string_list(expression.get("values")))
    return sorted(set(hostnames))


def _persistent_volume_source_type(spec: Mapping[str, object]) -> str | None:
    """Return the first recognized volume-source type present on a PV spec."""

    for candidate in (
        "csi",
        "hostPath",
        "local",
        "nfs",
        "awsElasticBlockStore",
        "gcePersistentDisk",
    ):
        if isinstance(spec.get(candidate), dict):
            return candidate
    return None


def _items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, object]] = []
    typed_items = cast(list[object], raw_items)
    for item in typed_items:
        if isinstance(item, dict):
            items.append(cast(dict[str, object], item))
    return items


def _group_collection_path(
    *,
    cluster_id: str,
    api_group: str,
    api_version: str,
    resource: str,
) -> str:
    """Build one raw Kubernetes group-scoped collection path."""

    return (
        f"{_cluster_root(cluster_id)}/apis/{quote(api_group, safe='')}/"
        f"{quote(api_version, safe='')}/{quote(resource, safe='')}"
    )


def _core_collection_path(
    *,
    cluster_id: str,
    api_version: str,
    resource: str,
    namespace: str | None = None,
) -> str:
    """Build one raw Kubernetes core-API collection path."""

    base_path = f"{_cluster_root(cluster_id)}/api/{quote(api_version, safe='')}"
    if namespace is not None:
        return f"{base_path}/namespaces/{quote(namespace, safe='')}/{quote(resource, safe='')}"
    return f"{base_path}/{quote(resource, safe='')}"


def _cluster_root(cluster_id: str) -> str:
    """Return the Rancher raw Kubernetes proxy root for one cluster."""

    return f"/k8s/clusters/{quote(cluster_id, safe='')}"


def _append_identifier(path: str, identifier: str) -> str:
    """Append one quoted identifier to a relative path."""

    return f"{path.rstrip('/')}/{quote(identifier, safe='')}"


def _mapping_value(
    payload: Mapping[str, object] | None,
    key: str,
) -> dict[str, object] | None:
    """Read one nested mapping value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    if not isinstance(raw_value, dict):
        return None
    return cast(dict[str, object], raw_value)


def _string_value(payload: Mapping[str, object] | None, key: str) -> str | None:
    """Read one string value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, str) else None


def _bool_value(payload: Mapping[str, object] | None, key: str) -> bool | None:
    """Read one boolean value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, bool) else None


def _string_list(value: object) -> list[str]:
    """Normalize an arbitrary value into a list of strings."""

    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in cast(list[object], value):
        if isinstance(item, str):
            result.append(item)
    return result


def _string_dict(value: object) -> dict[str, str]:
    """Normalize an arbitrary value into a string-to-string mapping."""

    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, raw_value in cast(dict[object, object], value).items():
        if isinstance(key, str) and isinstance(raw_value, str):
            result[key] = raw_value
    return result


def _annotation_true(annotations: Mapping[str, object], key: str) -> bool | None:
    """Return one string annotation value normalized as a boolean when possible."""

    return _status_to_bool(_string_value(annotations, key))


def _status_to_bool(value: str | None) -> bool | None:
    """Normalize Kubernetes-style string booleans to actual booleans."""

    if value is None:
        return None
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None
