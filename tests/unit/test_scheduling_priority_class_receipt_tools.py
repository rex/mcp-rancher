"""M-A2 mutation-receipt enrichment tests for PriorityClass patch tools.

Split out of ``test_scheduling_priority_class_tools.py`` to stay under the
architecture line limit — the same rationale ``_scheduling_support.py``
documents for the original list/get vs set_labels/set_annotations split.
That file already covers the round-trip + audit contract for
``set_labels``/``set_annotations``; this file covers the M-A2 receipt
enrichment layered on top of every curated patch tool: the best-effort
``before`` snapshot (one extra GET immediately ahead of the patch) and the
``duration_ms`` patch timing.
"""

from __future__ import annotations

import pytest
from _scheduling_support import build_settings

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.scheduling import (
    rancher_priority_class_set_annotations,
    rancher_priority_class_set_labels,
)

_EXPECTED_PATCH_PATH = (
    "/k8s/clusters/local/apis/scheduling.k8s.io/v1/priorityclasses/system-critical"
)

_PATCHED_PRIORITY_CLASS_PAYLOAD = {
    "metadata": {
        "name": "system-critical",
        "labels": {"env": "prod"},
        "annotations": {"managed-by": "platform-team"},
    },
    "value": 1000000,
    "globalDefault": False,
    "preemptionPolicy": "PreemptLowerPriority",
    "description": "Used for system-critical pods",
}

_PRIOR_PRIORITY_CLASS_PAYLOAD = {
    "metadata": {
        "name": "system-critical",
        "labels": {"tier": "gold"},
        "annotations": {"app": "platform"},
    },
    "value": 1000000,
    "globalDefault": False,
    "preemptionPolicy": "PreemptLowerPriority",
    "description": "Used for system-critical pods",
}


class _StubBeforeFetchRaises:
    """Patch-capable stub whose get_json always raises (before-fetch failure).

    Proves the M-A2 before-snapshot is genuinely best-effort: the patch below
    must still go through and the receipt must still come back ok, just with
    ``before=None`` instead of the (unavailable) prior state.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Simulate a failed before-snapshot pre-fetch (network, auth, anything)."""

        raise AssertionError(f"simulated before-fetch failure on {path!r}")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and return a fake post-patch payload."""

        assert path == _EXPECTED_PATCH_PATH
        assert payload is not None
        self.last_patch_path = path
        self.last_patch_payload = dict(payload)
        return _PATCHED_PRIORITY_CLASS_PAYLOAD


class _StubBeforeFetchReturnsPriorState:
    """Patch-capable stub whose get_json answers the before-snapshot pre-fetch.

    Returns a known prior payload so the receipt's ``before`` can be asserted
    against a concrete expected value that mirrors ``changed`` key-for-key.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Answer the before-snapshot pre-fetch with the prior resource state."""

        assert path == _EXPECTED_PATCH_PATH
        assert params is None
        return _PRIOR_PRIORITY_CLASS_PAYLOAD

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and return a fake post-patch payload."""

        assert path == _EXPECTED_PATCH_PATH
        assert payload is not None
        self.last_patch_path = path
        self.last_patch_payload = dict(payload)
        return _PATCHED_PRIORITY_CLASS_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_priority_class_set_labels_captures_before_and_duration() -> None:
    """`before` mirrors the changed key with its PRIOR value; duration_ms is timed."""

    reset_rate_limit_state()

    result = await rancher_priority_class_set_labels(
        priority_class_name="system-critical",
        labels={"env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=_StubBeforeFetchReturnsPriorState(),
    )

    assert result.ok is True
    assert result.changed == {"labels": {"env": "prod"}}
    assert result.before == {"labels": {"tier": "gold"}}
    assert result.duration_ms is not None
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_rancher_priority_class_set_labels_before_snapshot_failure_ok() -> None:
    """A pre-fetch failure must never block the patch; the receipt gets before=None."""

    reset_rate_limit_state()
    client = _StubBeforeFetchRaises()

    result = await rancher_priority_class_set_labels(
        priority_class_name="system-critical",
        labels={"env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # The patch itself still went through despite the failed before-fetch.
    assert result.ok is True
    assert result.changed == {"labels": {"env": "prod"}}
    assert client.last_patch_payload == {"metadata": {"labels": {"env": "prod"}}}
    assert result.before is None
    assert result.duration_ms is not None
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_rancher_priority_class_set_annotations_captures_before_and_duration() -> None:
    """`before` mirrors the changed key with its PRIOR value; duration_ms is timed."""

    reset_rate_limit_state()

    result = await rancher_priority_class_set_annotations(
        priority_class_name="system-critical",
        annotations={"managed-by": "platform-team"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=_StubBeforeFetchReturnsPriorState(),
    )

    assert result.ok is True
    assert result.changed == {"annotations": {"managed-by": "platform-team"}}
    assert result.before == {"annotations": {"app": "platform"}}
    assert result.duration_ms is not None
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_rancher_priority_class_set_annotations_before_snapshot_failure_ok() -> None:
    """A pre-fetch failure must never block the patch; the receipt gets before=None."""

    reset_rate_limit_state()
    client = _StubBeforeFetchRaises()

    result = await rancher_priority_class_set_annotations(
        priority_class_name="system-critical",
        annotations={"managed-by": "platform-team"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert result.ok is True
    assert result.changed == {"annotations": {"managed-by": "platform-team"}}
    assert client.last_patch_payload == {
        "metadata": {"annotations": {"managed-by": "platform-team"}}
    }
    assert result.before is None
    assert result.duration_ms is not None
    assert result.duration_ms >= 0
