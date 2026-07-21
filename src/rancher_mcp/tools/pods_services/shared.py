"""Shared normalization helpers for curated pod and service tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import structlog

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.models.discovery import RancherInstanceConfig
from rancher_mcp.models.pods_services import (
    RancherPodContainerSummary,
    RancherPodEventSummary,
    RancherPodSummary,
    RancherServiceSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.conditions import (
    condition_is_true as _condition_is_true,
)
from rancher_mcp.tools.support.conditions import (
    conditions_from_payload as _conditions_from_status,
)
from rancher_mcp.tools.support.values import (
    int_value as _int_value,
)
from rancher_mcp.tools.support.values import (
    mapping_value as _mapping_value,
)
from rancher_mcp.tools.support.values import (
    string_list as _string_list,
)
from rancher_mcp.tools.support.values import (
    string_value as _string_value,
)

_logger = structlog.get_logger("rancher_mcp.tools.pods_services")

# Most-recent-first cap on `pod_get`'s inlined `events[]` (M-B4) — enough to
# diagnose a broken pod without repeating a namespace-wide events dump.
_POD_EVENTS_LIMIT = 10


def _pod_ready_from_status(status: Mapping[str, object]) -> bool | None:
    """Derive a pod's Ready condition from its raw ``status`` mapping.

    Shared by :func:`_pod_summary_from_payload` and the namespace/project
    rollups (``tools/ops/rollups.py``, M-A4) so both derive "is this pod
    ready" the same way, without either needing the full container-status
    parse that only the pod-detail surfaces require.
    """

    return _condition_is_true(_conditions_from_status(status), "Ready")


def _pod_summary_from_payload(payload: Mapping[str, object]) -> RancherPodSummary:
    """Normalize one pod payload."""

    summary = RancherPodSummary.model_validate(payload)
    status = _mapping_value(payload, "status") or {}
    containers = _container_summaries(status)
    return summary.model_copy(
        update={
            "ready_condition": _pod_ready_from_status(status),
            "ready_containers": sum(1 for container in containers if container.ready is True),
            "total_containers": len(containers),
            "restart_count": sum(container.restart_count or 0 for container in containers),
        }
    )


def _service_summary_from_payload(payload: Mapping[str, object]) -> RancherServiceSummary:
    """Normalize one service payload."""

    return RancherServiceSummary.model_validate(payload)


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher list payload."""

    return object_items(payload, field="data")


def _container_summaries(status: Mapping[str, object]) -> list[RancherPodContainerSummary]:
    """Normalize pod container statuses."""

    raw_statuses = status.get("containerStatuses")
    if not isinstance(raw_statuses, list):
        return []
    return [
        RancherPodContainerSummary.model_validate(raw_status)
        for raw_status in cast(list[object], raw_statuses)
        if isinstance(raw_status, dict)
    ]


def _relationship_types(metadata: Mapping[str, object]) -> list[str]:
    """Return sorted relationship targets from service metadata."""

    relationship_values: set[str] = set()
    for relationship in object_items(metadata, field="relationships"):
        to_type = relationship.get("toType")
        if to_type is not None:
            relationship_values.add(str(to_type))
        rel = relationship.get("rel")
        if rel is not None:
            relationship_values.add(str(rel))
    return sorted(relationship_values)


def _pod_events_field_selector(namespace: str, pod_name: str) -> str:
    """Build the ``involvedObject`` field selector scoping events to one pod."""

    return (
        f"involvedObject.name={pod_name},"
        f"involvedObject.namespace={namespace},"
        "involvedObject.kind=Pod"
    )


def _pod_event_summary(item: Mapping[str, object]) -> RancherPodEventSummary:
    """Normalize one raw Kubernetes event into the lean pod-inlined shape."""

    return RancherPodEventSummary(
        type=_string_value(item, "type"),
        reason=_string_value(item, "reason"),
        message=_string_value(item, "message"),
        count=_int_value(item, "count"),
        last_seen=_string_value(item, "lastTimestamp") or _string_value(item, "firstTimestamp"),
    )


async def _fetch_pod_events(
    client: ManagementDiscoveryClient,
    cluster_id: str,
    namespace: str,
    pod_name: str,
) -> list[RancherPodEventSummary]:
    """Fetch one pod's recent Kubernetes events, most-recent first, capped.

    Reuses the exact client + endpoint pattern ``rancher_cluster_events_list``
    uses (``tools/ops/events.py``: a k8s-proxy ``ManagementDiscoveryClient``
    against the namespaced core-API events collection, via
    ``tools/ops/paths.k8s_core_ns_path``/``k8s_items``) — narrowed server-side
    with an ``involvedObject`` field selector instead of a namespace-wide
    fetch, since `pod_get` only wants one pod's events.

    The `tools.ops.paths` import is deliberately deferred to inside this
    function rather than hoisted to module scope: `tools/ops/__init__.py`
    eagerly imports `tools/ops/rollups.py`, which itself imports from this
    module (`pod_ready_from_status`) — a module-level import here would
    complete a circular-import cycle through the `tools.ops` package `__init__`.
    Deferring it until call time (long after both packages have finished
    initializing) sidesteps the cycle without touching either package.
    """

    from rancher_mcp.tools.ops.paths import k8s_core_ns_path, k8s_items

    path = k8s_core_ns_path(cluster_id, namespace, "events")
    field_selector = _pod_events_field_selector(namespace, pod_name)
    payload = await client.get_json(path, params={"fieldSelector": field_selector})
    events = [_pod_event_summary(item) for item in k8s_items(payload)]
    events.sort(key=lambda event: event.last_seen or "", reverse=True)
    return events[:_POD_EVENTS_LIMIT]


async def _pod_events_best_effort(
    instance_name: str,
    instance_config: RancherInstanceConfig,
    cluster_id: str,
    namespace: str,
    pod_name: str,
) -> list[RancherPodEventSummary]:
    """Best-effort events fetch for `pod_get`'s inline ``events[]`` (M-B4).

    Opens a SECOND, k8s-proxy-plane client alongside the Steve-plane pod
    fetch (events live under the raw Kubernetes proxy, not Steve). Must
    NEVER break `pod_get`: any failure here — an unreachable tunnel, an
    endpoint unsupported on an older Rancher, a malformed response — is
    logged and swallowed, returning an empty list so `events` is simply
    omitted from the response (log-and-continue, not re-raise, by design).
    """

    try:
        async with RancherManagementClient(instance_name, instance_config) as managed_client:
            return await _fetch_pod_events(managed_client, cluster_id, namespace, pod_name)
    except Exception as exc:  # best-effort by design — see docstring
        _logger.warning(
            "pod_events_fetch_failed",
            instance=instance_name,
            cluster_id=cluster_id,
            namespace=namespace,
            pod_name=pod_name,
            error=str(exc),
            exc_info=True,
        )
        return []


conditions_from_status = _conditions_from_status
container_summaries = _container_summaries
data_items = _data_items
mapping_value = _mapping_value
pod_events_best_effort = _pod_events_best_effort
pod_ready_from_status = _pod_ready_from_status
pod_summary_from_payload = _pod_summary_from_payload
relationship_types = _relationship_types
service_summary_from_payload = _service_summary_from_payload
string_list = _string_list
