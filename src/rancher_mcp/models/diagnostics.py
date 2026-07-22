"""Typed models for curated diagnosis-verb tools (M-K7)."""

from __future__ import annotations

from pydantic import Field

from rancher_mcp.models.base import RancherModel


class RancherPodLogResult(RancherModel):
    """Typed result for one pod container's recent log tail (M-K7).

    ``truncated`` is the honest completeness signal (ADR-0002 rule #2 —
    exception-shaped, never silently partial): True whenever the returned
    line count reaches the requested ``tail_lines`` cap, meaning earlier log
    lines may exist beyond what's returned. The raw Kubernetes log endpoint
    has no "was this the whole log" signal to query, so this mirrors
    `kubectl logs --tail=N`'s own honest ambiguity rather than asserting a
    completeness it can't verify.
    """

    instance: str
    cluster_id: str
    namespace: str
    pod_name: str
    container: str
    tail_lines: int
    previous: bool
    truncated: bool
    line_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    lines: list[str] = Field(default_factory=list)
