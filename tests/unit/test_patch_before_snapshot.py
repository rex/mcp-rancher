"""Unit tests for the M-A2 before-snapshot helpers (tools/support/mutations.py).

``patch_before_snapshot`` is the pure extraction primitive; ``fetch_patch_before``
is the best-effort async wrapper the codegen template calls from every curated
patch tool, immediately ahead of the merge-patch request. Covered directly
here (fast, no client/codegen plumbing) in addition to the end-to-end
coverage in the scheduling patch test suite
(``test_scheduling_priority_class_tools.py``).
"""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from rancher_mcp.tools.support.mutations import fetch_patch_before, patch_before_snapshot


def test_patch_before_snapshot_extracts_nested_target_path() -> None:
    """set_labels-shaped patch: target_path=metadata, changed key `labels`."""

    payload = {
        "metadata": {"name": "api", "labels": {"tier": "gold"}, "annotations": {}},
        "spec": {"replicas": 2},
    }

    before = patch_before_snapshot(payload, "metadata", {"labels": {"env": "prod"}})

    assert before == {"labels": {"tier": "gold"}}


def test_patch_before_snapshot_empty_target_path_reads_root() -> None:
    """target_path="" (a top-level patch) reads straight off the payload root."""

    payload = {"paused": False, "other": "noise"}

    before = patch_before_snapshot(payload, "", {"paused": True})

    assert before == {"paused": False}


def test_patch_before_snapshot_missing_key_reads_none() -> None:
    """A key with no prior value reads as None rather than being omitted or raising."""

    payload = {"metadata": {"name": "api"}}  # no prior labels

    before = patch_before_snapshot(payload, "metadata", {"labels": {"env": "prod"}})

    assert before == {"labels": None}


def test_patch_before_snapshot_missing_path_segment_reads_none() -> None:
    """An absent target_path segment degrades to None per key, not a raise."""

    payload = {"unrelated": {"foo": "bar"}}

    before = patch_before_snapshot(payload, "spec", {"replicas": 4})

    assert before == {"replicas": None}


def test_patch_before_snapshot_none_payload_is_total() -> None:
    """A None payload (defensive) still returns a dict of Nones, never raises."""

    before = patch_before_snapshot(None, "metadata", {"labels": {}})

    assert before == {"labels": None}


def test_patch_before_snapshot_mirrors_multiple_changed_keys() -> None:
    """A multi-key patch subtree (e.g. a restart's nested template) mirrors every key."""

    payload = {"spec": {"template": {"metadata": {"annotations": {"a": "1"}}}, "replicas": 3}}

    before = patch_before_snapshot(
        payload,
        "spec",
        {"template": {}, "replicas": 0},
    )

    assert before == {
        "template": {"metadata": {"annotations": {"a": "1"}}},
        "replicas": 3,
    }


@pytest.mark.asyncio
async def test_fetch_patch_before_success_returns_snapshot() -> None:
    """The happy path: fetch_current resolves and the snapshot is extracted."""

    async def _fetch_current() -> dict[str, object]:
        return {"metadata": {"labels": {"tier": "gold"}}}

    before = await fetch_patch_before(
        _fetch_current,
        target_path="metadata",
        patch_subtree={"labels": {"env": "prod"}},
        kind="deployment",
        action="set_labels",
        name="api",
    )

    assert before == {"labels": {"tier": "gold"}}


@pytest.mark.asyncio
async def test_fetch_patch_before_swallows_any_failure() -> None:
    """ANY exception from fetch_current must degrade to before=None, never raise."""

    async def _fetch_current() -> dict[str, object]:
        raise RuntimeError("tunnel dropped mid-GET")

    before = await fetch_patch_before(
        _fetch_current,
        target_path="metadata",
        patch_subtree={"labels": {"env": "prod"}},
        kind="deployment",
        action="set_labels",
        name="api",
    )

    assert before is None


@pytest.mark.asyncio
async def test_fetch_patch_before_logs_the_swallowed_failure() -> None:
    """The swallowed failure is still observable via a structured warning log."""

    async def _fetch_current() -> dict[str, object]:
        raise RuntimeError("boom")

    with capture_logs() as logs:
        before = await fetch_patch_before(
            _fetch_current,
            target_path="metadata",
            patch_subtree={"labels": {}},
            kind="deployment",
            action="set_labels",
            name="api",
        )

    assert before is None
    failures = [r for r in logs if r.get("event") == "patch_before_snapshot_failed"]
    assert len(failures) == 1
    assert failures[0]["kind"] == "deployment"
    assert failures[0]["action"] == "set_labels"
    assert failures[0]["name"] == "api"
