"""Raw Kubernetes proxy paths for policy reports (wgpolicyk8s.io/v1alpha2)."""

from __future__ import annotations

from urllib.parse import quote


def _policy_namespaced_collection_path(
    cluster_id: str, namespace: str | None, resource: str
) -> str:
    """Build the collection path for a wgpolicyk8s.io/v1alpha2 resource.

    All-namespaces (the namespace segment dropped) when ``namespace`` is
    ``None`` — the cluster-wide triage form."""

    base = f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/wgpolicyk8s.io/v1alpha2/"
    if namespace is not None:
        base += f"namespaces/{quote(namespace, safe='')}/"
    return base + quote(resource, safe="")


def _policy_namespaced_resource_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
) -> str:
    """Build the namespaced resource path for a wgpolicyk8s.io/v1alpha2 resource."""

    return (
        f"{_policy_namespaced_collection_path(cluster_id, namespace, resource)}/"
        f"{quote(name, safe='')}"
    )


def _policy_cluster_collection_path(cluster_id: str, resource: str) -> str:
    """Build the cluster-scoped collection path for a wgpolicyk8s.io/v1alpha2 resource."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/wgpolicyk8s.io/v1alpha2/"
        f"{quote(resource, safe='')}"
    )


def _policy_cluster_resource_path(cluster_id: str, resource: str, name: str) -> str:
    """Build the cluster-scoped resource path for a wgpolicyk8s.io/v1alpha2 resource."""

    return f"{_policy_cluster_collection_path(cluster_id, resource)}/{quote(name, safe='')}"


policy_cluster_collection_path = _policy_cluster_collection_path
policy_cluster_resource_path = _policy_cluster_resource_path
policy_namespaced_collection_path = _policy_namespaced_collection_path
policy_namespaced_resource_path = _policy_namespaced_resource_path
