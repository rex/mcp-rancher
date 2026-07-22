"""Any-resource Kubernetes events — "what just happened to this thing" (M-K7).

Generalizes M-B4's pod-scoped best-effort events fetch
(`tools/pods_services/shared.py`'s `_fetch_pod_events`) to an arbitrary
namespaced `kind`/`name`, reusing the exact same field-selector + k8s-proxy
client approach via `tools/support/k8s_events.py` rather than duplicating
it. Hand-written (not codegen) — a new operator verb, not generic CRUD.
"""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.ops.events import RancherResourceEventList, RancherResourceEventSummary
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.ops.paths import k8s_core_ns_path, k8s_items
from rancher_mcp.tools.support.k8s_events import (
    event_summary_fields,
    involved_object_field_selector,
)

# Most-recent-first cap — enough to diagnose without a namespace-wide dump
# (same rationale as M-B4's pod-inlined events cap in
# `tools/pods_services/shared.py`, just a slightly wider window since this
# tool has no surrounding resource detail to fall back on).
_RESOURCE_EVENTS_LIMIT = 20


def _resource_event_summary(item: dict[str, object]) -> RancherResourceEventSummary:
    """Normalize one raw Kubernetes event into the lean any-kind shape."""

    return RancherResourceEventSummary(**event_summary_fields(item))


async def _fetch_resource_events(
    client: ManagementDiscoveryClient,
    instance_name: str,
    cluster_id: str,
    namespace: str,
    kind: str,
    name: str,
) -> RancherResourceEventList:
    """Fetch and normalize recent events for one named namespaced resource."""

    path = k8s_core_ns_path(cluster_id, namespace, "events")
    field_selector = involved_object_field_selector(namespace, name, kind)
    payload = await client.get_json(path, params={"fieldSelector": field_selector})
    events = [_resource_event_summary(item) for item in k8s_items(payload)]
    events.sort(key=lambda event: event.last_seen or "", reverse=True)
    capped = events[:_RESOURCE_EVENTS_LIMIT]

    return RancherResourceEventList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        kind=kind,
        name=name,
        event_count=len(capped),
        events=capped,
    )


async def rancher_resource_events(
    namespace: str,
    name: str,
    kind: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherResourceEventList:
    """List recent Kubernetes events for one named resource (testable core)."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_resource_events(
            client, instance_name, cluster_id, namespace, kind, name
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_resource_events(
            managed_client, instance_name, cluster_id, namespace, kind, name
        )


async def rancher_resource_events_tool(
    namespace: str,
    name: str,
    kind: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherResourceEventList:
    """List recent Kubernetes events for one named resource (Pod, Deployment,
    PersistentVolumeClaim, ...) — "what just happened to this thing",
    generalized from `pod_get`'s inlined pod-scoped events to any `kind`.
    Most recent first, capped to the last ~20."""

    return await rancher_resource_events(
        namespace=namespace,
        name=name,
        kind=kind,
        cluster_id=cluster_id,
        instance=instance,
    )
