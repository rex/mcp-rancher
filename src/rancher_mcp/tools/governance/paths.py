"""Raw Kubernetes proxy paths for cluster-governance resources.

HPA lives at ``autoscaling/v2``; ResourceQuota and LimitRange live in
the core API at ``api/v1``.
"""

from __future__ import annotations

from urllib.parse import quote


def _autoscaling_v2_collection_path(cluster_id: str, namespace: str, resource: str) -> str:
    """Build the namespaced collection path for an autoscaling/v2 resource."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/autoscaling/v2/"
        f"namespaces/{quote(namespace, safe='')}/{quote(resource, safe='')}"
    )


def _autoscaling_v2_resource_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
) -> str:
    """Build the namespaced resource path for an autoscaling/v2 resource."""

    return (
        f"{_autoscaling_v2_collection_path(cluster_id, namespace, resource)}/{quote(name, safe='')}"
    )


def _core_v1_collection_path(cluster_id: str, namespace: str, resource: str) -> str:
    """Build the namespaced collection path for a core/v1 resource (api/v1)."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/api/v1/"
        f"namespaces/{quote(namespace, safe='')}/{quote(resource, safe='')}"
    )


def _core_v1_resource_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
) -> str:
    """Build the namespaced resource path for a core/v1 resource."""

    return f"{_core_v1_collection_path(cluster_id, namespace, resource)}/{quote(name, safe='')}"


autoscaling_v2_collection_path = _autoscaling_v2_collection_path
autoscaling_v2_resource_path = _autoscaling_v2_resource_path
core_v1_collection_path = _core_v1_collection_path
core_v1_resource_path = _core_v1_resource_path
