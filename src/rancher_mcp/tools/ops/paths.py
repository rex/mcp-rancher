"""Raw Kubernetes proxy path helpers for ops tools."""

from __future__ import annotations

from typing import cast
from urllib.parse import quote


def k8s_core_ns_path(cluster_id: str, namespace: str, resource: str) -> str:
    """Build a raw Kubernetes proxy core-API namespaced path."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/api/v1/"
        f"namespaces/{quote(namespace, safe='')}/{quote(resource, safe='')}"
    )


def k8s_apps_ns_path(cluster_id: str, namespace: str, resource: str) -> str:
    """Build a raw Kubernetes proxy apps/v1 namespaced path."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/apps/v1/"
        f"namespaces/{quote(namespace, safe='')}/{quote(resource, safe='')}"
    )


def k8s_policy_ns_path(cluster_id: str, namespace: str, resource: str) -> str:
    """Build a raw Kubernetes proxy policy/v1 namespaced path."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/policy/v1/"
        f"namespaces/{quote(namespace, safe='')}/{quote(resource, safe='')}"
    )


def k8s_items(payload: dict[str, object]) -> list[dict[str, object]]:
    """Extract items from a raw Kubernetes list payload."""

    raw = payload.get("items")
    if not isinstance(raw, list):
        return []
    return [item for item in cast(list[object], raw) if isinstance(item, dict)]
