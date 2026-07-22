"""Shared Kubernetes event helpers: field selector + lean item shape.

Both the pod-scoped best-effort events fetch
(`tools/pods_services/shared.py`'s `_fetch_pod_events`, M-B4) and the
any-``kind``-scoped `resource_events` tool
(`tools/diagnostics/resource_events.py`, M-K7) fetch the same raw
Kubernetes Event collection via a server-side ``involvedObject`` field
selector and normalize the same handful of fields onto a lean per-event
shape. This module is the one place that logic lives so neither call site
duplicates it (ADR-0002: shared mechanisms over per-tool hand-rolling).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict

from rancher_mcp.tools.support.values import int_value, string_value


class EventSummaryFields(TypedDict):
    """The common lean per-event field set, typed for ``**``-unpacking into
    either :class:`~rancher_mcp.models.pods_services.RancherPodEventSummary`
    or :class:`~rancher_mcp.models.ops.events.RancherResourceEventSummary` —
    both share this exact field set by design, so both constructors accept
    it verbatim under strict type checking."""

    type: str | None
    reason: str | None
    message: str | None
    count: int | None
    last_seen: str | None


def involved_object_field_selector(namespace: str, name: str, kind: str) -> str:
    """Build the ``involvedObject`` field selector scoping events to one resource."""

    return (
        f"involvedObject.name={name},"
        f"involvedObject.namespace={namespace},"
        f"involvedObject.kind={kind}"
    )


def event_summary_fields(item: Mapping[str, object]) -> EventSummaryFields:
    """Extract the common lean event fields from one raw Kubernetes Event."""

    return EventSummaryFields(
        type=string_value(item, "type"),
        reason=string_value(item, "reason"),
        message=string_value(item, "message"),
        count=int_value(item, "count"),
        last_seen=string_value(item, "lastTimestamp") or string_value(item, "firstTimestamp"),
    )
