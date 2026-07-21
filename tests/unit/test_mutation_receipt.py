"""Mutation-receipt tests (ROADMAP L-1 / ADR-0002).

Metadata/state mutations return a compact receipt — success, what changed —
instead of the full curated detail (a 1-3 KB object). Deletes keep their own
RancherCuratedDeleteResult.
"""

from __future__ import annotations

from rancher_mcp.models.resources import RancherMutationReceipt


def test_receipt_is_compact_and_reports_what_changed() -> None:
    dumped = RancherMutationReceipt(
        instance="work",
        plane="steve",
        action="scale",
        kind="deployment",
        cluster_id="c-x",
        namespace="kong",
        name="api",
        changed={"replicas": 4},
    ).model_dump(by_alias=True)

    assert dumped["ok"] is True
    assert dumped["action"] == "scale"
    assert dumped["kind"] == "deployment"
    assert dumped["name"] == "api"
    assert dumped["changed"] == {"replicas": 4}
    # No full-object bloat: the receipt carries no payload/detail fields.
    assert "payload" not in dumped


def test_receipt_empty_change_collapses_via_envelope() -> None:
    # Clearing labels (empty change) collapses — the L-0 envelope drops empty {}.
    dumped = RancherMutationReceipt(
        instance="work",
        plane="steve",
        action="set_labels",
        kind="deployment",
        name="api",
        changed={},
    ).model_dump(by_alias=True)

    assert "changed" not in dumped  # empty → omitted
    assert dumped["action"] == "set_labels"
