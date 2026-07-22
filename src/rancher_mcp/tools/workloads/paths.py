"""Raw Kubernetes proxy paths for workload controllers."""

from __future__ import annotations

from urllib.parse import quote


def workload_collection_path(cluster_id: str, namespace: str | None, resource: str) -> str:
    """Build the raw Kubernetes proxy collection path for one workload resource.

    All-namespaces (the namespace segment dropped) when ``namespace`` is
    ``None`` — the cluster-wide triage form."""

    base = f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/apps/v1/"
    if namespace is not None:
        base += f"namespaces/{quote(namespace, safe='')}/"
    return base + quote(resource, safe="")


def workload_resource_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
) -> str:
    """Build the raw Kubernetes proxy resource path for one workload object."""

    return f"{workload_collection_path(cluster_id, namespace, resource)}/{quote(name, safe='')}"
