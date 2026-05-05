"""Raw Kubernetes proxy paths for curated config-and-secrets tools."""

from __future__ import annotations

from urllib.parse import quote


def _core_v1_collection_path(cluster_id: str, namespace: str, resource: str) -> str:
    """Build the raw Kubernetes proxy collection path for a core-API namespaced resource."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/api/v1/namespaces/"
        f"{quote(namespace, safe='')}/{quote(resource, safe='')}"
    )


def _core_v1_resource_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
) -> str:
    """Build the raw Kubernetes proxy resource path for a core-API namespaced resource."""

    return f"{_core_v1_collection_path(cluster_id, namespace, resource)}/{quote(name, safe='')}"


core_v1_collection_path = _core_v1_collection_path
core_v1_resource_path = _core_v1_resource_path
