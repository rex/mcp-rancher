"""Raw Kubernetes proxy paths for Banzai Logging Operator (logging.banzaicloud.io/v1beta1).

Output / Flow are namespaced; ClusterOutput / ClusterFlow are
cluster-scoped.
"""

from __future__ import annotations

from urllib.parse import quote


def _logging_namespaced_collection_path(
    cluster_id: str, namespace: str | None, resource: str
) -> str:
    """Build the collection path for a logging.banzaicloud.io/v1beta1 resource.

    All-namespaces (the namespace segment dropped) when ``namespace`` is
    ``None`` — the cluster-wide triage form."""

    base = f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/logging.banzaicloud.io/v1beta1/"
    if namespace is not None:
        base += f"namespaces/{quote(namespace, safe='')}/"
    return base + quote(resource, safe="")


def _logging_namespaced_resource_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
) -> str:
    """Build the namespaced resource path for a logging.banzaicloud.io/v1beta1 resource."""

    return (
        f"{_logging_namespaced_collection_path(cluster_id, namespace, resource)}/"
        f"{quote(name, safe='')}"
    )


def _logging_cluster_collection_path(cluster_id: str, resource: str) -> str:
    """Build the cluster-scoped collection path for a logging.banzaicloud.io/v1beta1 resource."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/logging.banzaicloud.io/v1beta1/"
        f"{quote(resource, safe='')}"
    )


def _logging_cluster_resource_path(cluster_id: str, resource: str, name: str) -> str:
    """Build the cluster-scoped resource path for a logging.banzaicloud.io/v1beta1 resource."""

    return f"{_logging_cluster_collection_path(cluster_id, resource)}/{quote(name, safe='')}"


logging_cluster_collection_path = _logging_cluster_collection_path
logging_cluster_resource_path = _logging_cluster_resource_path
logging_namespaced_collection_path = _logging_namespaced_collection_path
logging_namespaced_resource_path = _logging_namespaced_resource_path
