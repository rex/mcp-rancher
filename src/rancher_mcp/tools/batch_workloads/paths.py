"""Raw Kubernetes proxy paths for batch/v1 resources."""

from __future__ import annotations

from urllib.parse import quote


def _batch_v1_collection_path(cluster_id: str, namespace: str | None, resource: str) -> str:
    """Build the collection path for a batch/v1 resource.

    All-namespaces (the namespace segment dropped) when ``namespace`` is
    ``None`` — the cluster-wide triage form."""

    base = f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/batch/v1/"
    if namespace is not None:
        base += f"namespaces/{quote(namespace, safe='')}/"
    return base + quote(resource, safe="")


def _batch_v1_resource_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
) -> str:
    """Build the namespaced resource path for a batch/v1 resource."""

    return f"{_batch_v1_collection_path(cluster_id, namespace, resource)}/{quote(name, safe='')}"


batch_v1_collection_path = _batch_v1_collection_path
batch_v1_resource_path = _batch_v1_resource_path
