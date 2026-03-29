"""Raw Kubernetes proxy paths for curated storage tools."""

from __future__ import annotations

from urllib.parse import quote


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


persistent_volume_claim_collection_path = _persistent_volume_claim_collection_path
persistent_volume_claim_resource_path = _persistent_volume_claim_resource_path
persistent_volume_collection_path = _persistent_volume_collection_path
persistent_volume_resource_path = _persistent_volume_resource_path
storage_class_collection_path = _storage_class_collection_path
storage_class_resource_path = _storage_class_resource_path
