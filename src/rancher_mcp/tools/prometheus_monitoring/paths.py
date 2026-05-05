"""Raw Kubernetes proxy paths for Prometheus Operator CRDs."""

from __future__ import annotations

from urllib.parse import quote


def _monitoring_namespaced_collection_path(cluster_id: str, namespace: str, resource: str) -> str:
    """Build the namespaced collection path for a monitoring.coreos.com/v1 resource."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/monitoring.coreos.com/v1/"
        f"namespaces/{quote(namespace, safe='')}/{quote(resource, safe='')}"
    )


def _monitoring_namespaced_resource_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
) -> str:
    """Build the namespaced resource path for a monitoring.coreos.com/v1 resource."""

    return (
        f"{_monitoring_namespaced_collection_path(cluster_id, namespace, resource)}/"
        f"{quote(name, safe='')}"
    )


monitoring_namespaced_collection_path = _monitoring_namespaced_collection_path
monitoring_namespaced_resource_path = _monitoring_namespaced_resource_path
