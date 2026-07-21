"""Derived-signal helpers for curated response shaping (ROADMAP L-2·0 / ADR-0002).

ADR-0002 rule #3 ("derive it for me"): the agent must never do arithmetic on a
response. These pure helpers turn raw Kubernetes/Rancher values into the derived
signal the L-2 hand-tunes surface — day counts, collapsed tokens, and a
condition severity — so every tool derives them the same way. The pure quantity
math (``parse_quantity`` / ``humanize_memory`` / ``percent``) lives in
:mod:`rancher_mcp.units` so the models layer can use it too; it is re-exported
here for tool-layer callers.

Dependency-free (stdlib only) and pure.
"""

from __future__ import annotations

from datetime import UTC, datetime

from rancher_mcp.tools.support.values import status_to_bool
from rancher_mcp.units import humanize_memory, parse_quantity, percent

__all__ = [
    "age_days",
    "condition_severity",
    "humanize_memory",
    "owner_token",
    "parse_quantity",
    "percent",
    "ready_token",
]


def age_days(timestamp: str | None, *, now: datetime | None = None) -> int | None:
    """Whole days between an ISO-8601/RFC3339 timestamp and now (UTC floor at 0)."""

    if not isinstance(timestamp, str) or not timestamp:
        return None
    try:
        moment = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    reference = now or datetime.now(UTC)
    return max(0, (reference - moment).days)


def ready_token(ready: int | None, total: int | None) -> str | None:
    """Collapse a ready/total pair into one token (``2/2``)."""

    if ready is None or total is None:
        return None
    return f"{ready}/{total}"


def owner_token(kind: str | None, name: str | None) -> str | None:
    """Collapse an owner reference into one token (``ReplicaSet/foo``)."""

    if not kind or not name:
        return None
    return f"{kind}/{name}"


# Condition types that mean the resource is *down* when not True (critical);
# a small set that is merely informational; everything else defaults to warning.
_CRITICAL_WHEN_NOT_TRUE = frozenset(
    {"ready", "available", "initialized", "containersready", "podscheduled"}
)
_INFO_WHEN_NOT_TRUE = frozenset({"agenttlsstrictcheck"})


def condition_severity(condition_type: str | None, status: str | None) -> str:
    """Classify a condition into ``critical`` / ``warning`` / ``info``.

    A *True* condition is healthy (``info``). A failing core-readiness condition
    (Ready/Available/…) is ``critical``; a known-cosmetic one is ``info``; any
    other failing condition defaults to ``warning`` — so "monitoring addon
    absent" and "Ready=False" no longer both read as a bare ``healthy:false``.
    """

    if status_to_bool(status) is True:
        return "info"
    key = "".join(ch for ch in (condition_type or "").lower() if ch.isalnum())
    if key in _CRITICAL_WHEN_NOT_TRUE:
        return "critical"
    if key in _INFO_WHEN_NOT_TRUE:
        return "info"
    return "warning"
