"""Raw Kubernetes proxy path helpers for ops tools."""

from __future__ import annotations

from typing import cast
from urllib.parse import quote


def _k8s_path(cluster_id: str, api_prefix: str, resource: str, namespace: str | None) -> str:
    """Build a raw Kubernetes proxy path.

    Namespaced when ``namespace`` is given; all-namespaces (the segment
    dropped) when it is ``None`` — the cluster-wide triage form (ROADMAP K-4).
    """

    base = f"/k8s/clusters/{quote(cluster_id, safe='')}/{api_prefix}/"
    if namespace is not None:
        base += f"namespaces/{quote(namespace, safe='')}/"
    return base + quote(resource, safe="")


def k8s_core_path(cluster_id: str, resource: str, namespace: str | None = None) -> str:
    """Core-API (api/v1) path; all-namespaces when ``namespace`` is None."""

    return _k8s_path(cluster_id, "api/v1", resource, namespace)


def k8s_apps_path(cluster_id: str, resource: str, namespace: str | None = None) -> str:
    """apps/v1 path; all-namespaces when ``namespace`` is None."""

    return _k8s_path(cluster_id, "apis/apps/v1", resource, namespace)


def k8s_policy_path(cluster_id: str, resource: str, namespace: str | None = None) -> str:
    """policy/v1 path; all-namespaces when ``namespace`` is None."""

    return _k8s_path(cluster_id, "apis/policy/v1", resource, namespace)


def k8s_core_ns_path(cluster_id: str, namespace: str, resource: str) -> str:
    """Namespaced core-API path (kept for the events/rollups call sites)."""

    return k8s_core_path(cluster_id, resource, namespace)


def k8s_core_named_path(
    cluster_id: str,
    namespace: str,
    resource: str,
    name: str,
    subresource: str | None = None,
) -> str:
    """Namespaced core-API path addressing one named resource, optionally
    with a subresource (e.g. a pod's ``log``, M-K7 diagnostics).

    Unlike ``k8s_core_ns_path`` (a collection path meant to be filtered with
    a query-string field selector), every segment here is quoted
    independently so a ``name``/``subresource`` value is never accidentally
    swallowed by the single ``quote(resource, safe="")`` the collection-path
    helpers above use.
    """

    base = (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/api/v1/"
        f"namespaces/{quote(namespace, safe='')}/"
        f"{quote(resource, safe='')}/{quote(name, safe='')}"
    )
    if subresource:
        base += f"/{quote(subresource, safe='')}"
    return base


def k8s_apps_ns_path(cluster_id: str, namespace: str, resource: str) -> str:
    """Namespaced apps/v1 path (kept for the rollups call sites)."""

    return k8s_apps_path(cluster_id, resource, namespace)


def k8s_policy_ns_path(cluster_id: str, namespace: str, resource: str) -> str:
    """Namespaced policy/v1 path."""

    return k8s_policy_path(cluster_id, resource, namespace)


def k8s_items(payload: dict[str, object]) -> list[dict[str, object]]:
    """Extract items from a raw Kubernetes list payload."""

    raw = payload.get("items")
    if not isinstance(raw, list):
        return []
    return [item for item in cast(list[object], raw) if isinstance(item, dict)]
