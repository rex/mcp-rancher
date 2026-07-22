"""Raw Kubernetes proxy paths for cert-manager CRDs (cert-manager.io/v1)."""

from __future__ import annotations

from urllib.parse import quote


def _cert_manager_namespaced_collection_path(
    cluster_id: str, namespace: str | None, resource: str
) -> str:
    """Build the collection path for a cert-manager.io/v1 resource.

    All-namespaces (the namespace segment dropped) when ``namespace`` is
    ``None`` — the cluster-wide triage form."""

    base = f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/cert-manager.io/v1/"
    if namespace is not None:
        base += f"namespaces/{quote(namespace, safe='')}/"
    return base + quote(resource, safe="")


def _cert_manager_namespaced_resource_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
) -> str:
    """Build the namespaced resource path for a cert-manager.io/v1 resource."""

    return (
        f"{_cert_manager_namespaced_collection_path(cluster_id, namespace, resource)}/"
        f"{quote(name, safe='')}"
    )


def _cert_manager_cluster_collection_path(cluster_id: str, resource: str) -> str:
    """Build the cluster-scoped collection path for a cert-manager.io/v1 resource."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/cert-manager.io/v1/"
        f"{quote(resource, safe='')}"
    )


def _cert_manager_cluster_resource_path(cluster_id: str, resource: str, name: str) -> str:
    """Build the cluster-scoped resource path for a cert-manager.io/v1 resource."""

    return f"{_cert_manager_cluster_collection_path(cluster_id, resource)}/{quote(name, safe='')}"


cert_manager_cluster_collection_path = _cert_manager_cluster_collection_path
cert_manager_cluster_resource_path = _cert_manager_cluster_resource_path
cert_manager_namespaced_collection_path = _cert_manager_namespaced_collection_path
cert_manager_namespaced_resource_path = _cert_manager_namespaced_resource_path
