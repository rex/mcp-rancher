"""Typed models for Kubernetes event tools."""

from __future__ import annotations

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def _empty_events() -> list[RancherEventSummary]:
    return []


class RancherEventSummary(RancherModel):
    """Typed summary for one Kubernetes event."""

    name: str = "<unknown-event>"
    namespace: str = "<unknown-namespace>"
    reason: str | None = None
    message: str | None = None
    event_type: str | None = None
    count: int | None = None
    involved_kind: str | None = None
    involved_name: str | None = None
    first_timestamp: str | None = None
    last_timestamp: str | None = None


class RancherEventList(RancherModel):
    """Typed list response for Kubernetes events."""

    instance: str
    cluster_id: str
    namespace: str | None
    event_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    events: list[RancherEventSummary] = Field(default_factory=_empty_events)


class RancherResourceEventSummary(RancherModel):
    """Typed summary for one Kubernetes event scoped to an arbitrary named
    resource (M-K7's ``resource_events`` — the any-``kind`` generalization of
    the pod-scoped
    :class:`~rancher_mcp.models.pods_services.RancherPodEventSummary`,
    M-B4). Deliberately the same lean shape: the involved object
    (namespace/kind/name) is already known from the surrounding
    `resource_events` response, so repeating it per event would be pure
    plumbing (ADR-0002 rule #1 — "would this field ever change what I do
    next?")."""

    type: str | None = None
    reason: str | None = None
    message: str | None = None
    count: int | None = None
    last_seen: str | None = None


def _empty_resource_events() -> list[RancherResourceEventSummary]:
    return []


class RancherResourceEventList(RancherModel):
    """Typed result for `resource_events` (M-K7) — recent events for one
    named namespaced resource, most-recent first."""

    instance: str
    cluster_id: str
    namespace: str
    kind: str
    name: str
    event_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    events: list[RancherResourceEventSummary] = Field(default_factory=_empty_resource_events)
