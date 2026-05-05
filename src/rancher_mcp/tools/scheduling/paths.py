"""Raw Kubernetes proxy paths for scheduling primitives.

PriorityClass lives at ``scheduling.k8s.io/v1`` (cluster-scoped) and
RuntimeClass lives at ``node.k8s.io/v1`` (cluster-scoped).
"""

from __future__ import annotations

from urllib.parse import quote


def _scheduling_v1_collection_path(cluster_id: str, resource: str) -> str:
    """Build the cluster-scoped collection path for a scheduling.k8s.io/v1 resource."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/scheduling.k8s.io/v1/"
        f"{quote(resource, safe='')}"
    )


def _scheduling_v1_resource_path(cluster_id: str, resource: str, name: str) -> str:
    """Build the cluster-scoped resource path for a scheduling.k8s.io/v1 resource."""

    return f"{_scheduling_v1_collection_path(cluster_id, resource)}/{quote(name, safe='')}"


def _node_v1_collection_path(cluster_id: str, resource: str) -> str:
    """Build the cluster-scoped collection path for a node.k8s.io/v1 resource."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/node.k8s.io/v1/{quote(resource, safe='')}"
    )


def _node_v1_resource_path(cluster_id: str, resource: str, name: str) -> str:
    """Build the cluster-scoped resource path for a node.k8s.io/v1 resource."""

    return f"{_node_v1_collection_path(cluster_id, resource)}/{quote(name, safe='')}"


node_v1_collection_path = _node_v1_collection_path
node_v1_resource_path = _node_v1_resource_path
scheduling_v1_collection_path = _scheduling_v1_collection_path
scheduling_v1_resource_path = _scheduling_v1_resource_path
