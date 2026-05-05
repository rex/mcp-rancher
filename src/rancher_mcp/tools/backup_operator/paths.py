"""Raw Kubernetes proxy paths for Rancher Backup Operator (resources.cattle.io/v1).

Both Backup and Restore are cluster-scoped CRDs that live on the
Rancher local cluster (where the Backup Operator chart is installed).
"""

from __future__ import annotations

from urllib.parse import quote


def _resources_cattle_io_v1_collection_path(cluster_id: str, resource: str) -> str:
    """Build the cluster-scoped collection path for a resources.cattle.io/v1 resource."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/resources.cattle.io/v1/"
        f"{quote(resource, safe='')}"
    )


def _resources_cattle_io_v1_resource_path(
    cluster_id: str,
    resource: str,
    name: str,
) -> str:
    """Build the cluster-scoped resource path for a resources.cattle.io/v1 resource."""

    return f"{_resources_cattle_io_v1_collection_path(cluster_id, resource)}/{quote(name, safe='')}"


resources_cattle_io_v1_collection_path = _resources_cattle_io_v1_collection_path
resources_cattle_io_v1_resource_path = _resources_cattle_io_v1_resource_path
