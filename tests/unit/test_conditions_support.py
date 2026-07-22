"""Condition-surface tests: since/ageDays/reason/message universal on
RancherCondition + the shared parser (ROADMAP M-B1/B2 / ADR-0002).

``since``/``age_days`` are computed at dump time from ``last_transition_time``
(never re-derived per call site), so a single model change here is what makes
the signal universal across every ``RancherCondition``-typed surface in the
codebase (clusters, nodes, pods, namespaces, PDBs, cert-manager, workloads,
auth users, ...).
"""

from __future__ import annotations

from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.tools.support.conditions import conditions_from_payload, first_false_condition


def test_rancher_condition_dumps_since_age_days_reason_and_message() -> None:
    """A condition with a known lastTransitionTime dumps `since` + `ageDays`
    (derived) alongside `reason`/`message` — the M-B1/B2 always-on temporal
    signal. `lastTransitionTime` itself stays off the dump (not duplicated
    under two names)."""

    condition = RancherCondition(
        type="Ready",
        status="False",
        reason="KubeletNotReady",
        message="node is not responding",
        last_transition_time="2021-01-01T00:00:00Z",
    )

    # Attribute access (unaffected by the dump-time exclude).
    assert condition.last_transition_time == "2021-01-01T00:00:00Z"
    assert condition.since == "2021-01-01T00:00:00Z"
    assert condition.age_days is not None and condition.age_days > 1000

    dumped = condition.model_dump(by_alias=True)
    assert dumped["reason"] == "KubeletNotReady"
    assert dumped["message"] == "node is not responding"
    assert dumped["since"] == "2021-01-01T00:00:00Z"
    assert dumped["ageDays"] > 1000
    assert "lastTransitionTime" not in dumped  # not shipped twice under two names


def test_rancher_condition_healthy_true_still_carries_since_and_age_days() -> None:
    """Temporal context is always-on signal (ADR-0002) even for a healthy
    True condition — unlike reason/message, which stay conditional/absent
    when the source payload doesn't set them."""

    condition = RancherCondition(
        type="Ready",
        status="True",
        last_transition_time="2021-01-01T00:00:00Z",
    )

    dumped = condition.model_dump(by_alias=True)
    assert dumped["since"] == "2021-01-01T00:00:00Z"
    assert dumped["ageDays"] > 1000
    assert "reason" not in dumped  # envelope drops the None
    assert "message" not in dumped


def test_rancher_condition_without_last_transition_time_omits_since_and_age_days() -> None:
    """No `lastTransitionTime` in the source payload means `since`/`ageDays`
    are absent — dropped, never guessed or defaulted to zero."""

    condition = RancherCondition(type="Ready", status="True")
    dumped = condition.model_dump(by_alias=True)
    assert "since" not in dumped
    assert "ageDays" not in dumped


def test_conditions_from_payload_populates_all_four_fields() -> None:
    """The shared parser already threads reason/message/lastTransitionTime
    through; since/ageDays now ride for free via the model's computed fields
    — confirming no parser change was needed for the M-B1/B2 audit."""

    payload = {
        "conditions": [
            {
                "type": "Ready",
                "status": "False",
                "reason": "ClusterUnreachable",
                "message": "cannot reach cluster",
                "lastTransitionTime": "2021-01-01T00:00:00Z",
            }
        ]
    }

    conditions = conditions_from_payload(payload)
    assert len(conditions) == 1
    condition = conditions[0]
    assert condition.reason == "ClusterUnreachable"
    assert condition.message == "cannot reach cluster"
    assert condition.since == "2021-01-01T00:00:00Z"
    assert condition.age_days is not None and condition.age_days > 1000


def test_first_false_condition_returns_first_false_else_none() -> None:
    """Shared helper (M-B1/B2) used by finders with no single canonical
    condition type to key on (PVCs, PDBs)."""

    conditions = conditions_from_payload(
        {
            "conditions": [
                {"type": "Healthy", "status": "True"},
                {"type": "Resizing", "status": "False", "reason": "Pending"},
            ]
        }
    )
    problem = first_false_condition(conditions)
    assert problem is not None
    assert problem.type == "Resizing"
    assert problem.reason == "Pending"

    assert first_false_condition([]) is None

    all_true = conditions_from_payload({"conditions": [{"type": "Healthy", "status": "True"}]})
    assert first_false_condition(all_true) is None
