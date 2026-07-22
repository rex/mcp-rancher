"""Raw Kubernetes proxy paths for curated networking tools."""

from __future__ import annotations

from urllib.parse import quote


def _networking_v1_collection_path(cluster_id: str, namespace: str | None, resource: str) -> str:
    """Build the raw Kubernetes proxy collection path for a networking.k8s.io/v1 resource.

    All-namespaces (the namespace segment dropped) when ``namespace`` is
    ``None`` — the cluster-wide triage form."""

    base = f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/networking.k8s.io/v1/"
    if namespace is not None:
        base += f"namespaces/{quote(namespace, safe='')}/"
    return base + quote(resource, safe="")


def _networking_v1_resource_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
) -> str:
    """Build the raw Kubernetes proxy resource path for a networking.k8s.io/v1 resource."""

    return (
        f"{_networking_v1_collection_path(cluster_id, namespace, resource)}/{quote(name, safe='')}"
    )


def _discovery_v1_collection_path(cluster_id: str, namespace: str | None, resource: str) -> str:
    """Build the raw Kubernetes proxy collection path for a discovery.k8s.io/v1 resource.

    All-namespaces (the namespace segment dropped) when ``namespace`` is
    ``None`` — the cluster-wide triage form."""

    base = f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/discovery.k8s.io/v1/"
    if namespace is not None:
        base += f"namespaces/{quote(namespace, safe='')}/"
    return base + quote(resource, safe="")


def _discovery_v1_resource_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
) -> str:
    """Build the raw Kubernetes proxy resource path for a discovery.k8s.io/v1 resource."""

    return (
        f"{_discovery_v1_collection_path(cluster_id, namespace, resource)}/{quote(name, safe='')}"
    )


discovery_v1_collection_path = _discovery_v1_collection_path
discovery_v1_resource_path = _discovery_v1_resource_path
networking_v1_collection_path = _networking_v1_collection_path
networking_v1_resource_path = _networking_v1_resource_path
