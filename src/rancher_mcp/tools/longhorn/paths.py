"""Raw Kubernetes proxy paths for Longhorn (longhorn.io/v1beta2)."""

from __future__ import annotations

from urllib.parse import quote


def _longhorn_namespaced_collection_path(
    cluster_id: str, namespace: str | None, resource: str
) -> str:
    """Build the collection path for a longhorn.io/v1beta2 resource.

    All-namespaces (the namespace segment dropped) when ``namespace`` is
    ``None`` — the cluster-wide triage form."""

    base = f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/longhorn.io/v1beta2/"
    if namespace is not None:
        base += f"namespaces/{quote(namespace, safe='')}/"
    return base + quote(resource, safe="")


def _longhorn_namespaced_resource_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
) -> str:
    """Build the namespaced resource path for a longhorn.io/v1beta2 resource."""

    return (
        f"{_longhorn_namespaced_collection_path(cluster_id, namespace, resource)}/"
        f"{quote(name, safe='')}"
    )


longhorn_namespaced_collection_path = _longhorn_namespaced_collection_path
longhorn_namespaced_resource_path = _longhorn_namespaced_resource_path
