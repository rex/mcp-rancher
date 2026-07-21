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
