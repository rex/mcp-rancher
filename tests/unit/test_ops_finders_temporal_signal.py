"""Failure-finder reason/message/since/ageDays tests (ROADMAP M-B1/B2 / ADR-0002).

Split out from ``test_ops_find_tools.py`` to stay under the architecture line
limit (the repo's precedent: see ``test_workloads_deployments_shaping_tools.py``'s
own split-out docstring) — this module owns the M-B1/B2 temporal/diagnosis
enrichment specifically, one dedicated stub client per finder so each fixture
stays obviously scoped to exactly what it proves.
"""

from __future__ import annotations

import pytest
from _ops_support import build_settings

from rancher_mcp.tools.ops.find_failing_pods import rancher_find_failing_pods
from rancher_mcp.tools.ops.find_pdbs_blocking import rancher_find_pdbs_blocking
from rancher_mcp.tools.ops.find_stalled_rollouts import rancher_find_stalled_rollouts
from rancher_mcp.tools.ops.find_unbound_pvcs import rancher_find_unbound_pvcs
from rancher_mcp.tools.ops.find_unready_nodes import rancher_find_unready_nodes


class _CrashLoopPodClient:
    """Stub with one crash-looping pod: a waiting container state plus a
    Ready=False condition carrying a known lastTransitionTime."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        return {
            "items": [
                {
                    "metadata": {"name": "api-0", "namespace": "default"},
                    "spec": {"nodeName": "worker-1"},
                    "status": {
                        "phase": "Running",
                        "conditions": [
                            {
                                "type": "Ready",
                                "status": "False",
                                "reason": "ContainersNotReady",
                                "message": "containers with unready status: [api]",
                                "lastTransitionTime": "2021-01-01T00:00:00Z",
                            }
                        ],
                        "containerStatuses": [
                            {
                                "restartCount": 6,
                                "state": {
                                    "waiting": {
                                        "reason": "CrashLoopBackOff",
                                        "message": "back-off 5m0s restarting failed container",
                                    }
                                },
                            }
                        ],
                    },
                }
            ]
        }


@pytest.mark.asyncio
async def test_rancher_find_failing_pods_surfaces_message_since_and_age_days() -> None:
    """M-B1/B2: a crash-looping pod's `message` comes from the same waiting
    container state as `reason`; `since`/`ageDays` come from the pod's own
    Ready condition — no follow-up pod_get needed for either."""

    result = await rancher_find_failing_pods(
        namespace="default",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=_CrashLoopPodClient(),  # type: ignore[arg-type]
    )

    pod = result.pods[0]
    assert pod.reason == "CrashLoopBackOff"
    assert pod.message == "back-off 5m0s restarting failed container"
    assert pod.since == "2021-01-01T00:00:00Z"
    assert pod.age_days is not None and pod.age_days > 1000


class _UnreadyNodeConditionClient:
    """Stub with one NotReady node whose Ready condition carries a reason,
    message, and a known lastTransitionTime."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        assert path == "/v3/nodes"
        return {
            "data": [
                {
                    "id": "local:worker-2",
                    "name": "worker-2",
                    "state": "active",
                    "worker": True,
                    "unschedulable": False,
                    "conditions": [
                        {
                            "type": "Ready",
                            "status": "False",
                            "reason": "KubeletNotReady",
                            "message": "PLEG is not healthy",
                            "lastTransitionTime": "2021-01-01T00:00:00Z",
                        }
                    ],
                }
            ]
        }


@pytest.mark.asyncio
async def test_rancher_find_unready_nodes_surfaces_reason_since_and_age_days() -> None:
    """M-B1/B2: an unready node's `reason`/`since`/`ageDays` come from its own
    Ready condition, alongside the pre-existing `ready_condition_message`."""

    result = await rancher_find_unready_nodes(
        instance="work",
        settings=build_settings(),
        client=_UnreadyNodeConditionClient(),  # type: ignore[arg-type]
    )

    node = result.nodes[0]
    assert node.reason == "KubeletNotReady"
    assert node.ready_condition_message == "PLEG is not healthy"
    assert node.since == "2021-01-01T00:00:00Z"
    assert node.age_days is not None and node.age_days > 1000


class _StalledRolloutConditionClient:
    """Stub with one stalled deployment (ProgressDeadlineExceeded) and an
    empty statefulset collection."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        if path.endswith("/deployments"):
            return {
                "items": [
                    {
                        "metadata": {"name": "worker", "namespace": "default"},
                        "spec": {"replicas": 3},
                        "status": {
                            "readyReplicas": 1,
                            "updatedReplicas": 1,
                            "conditions": [
                                {
                                    "type": "Progressing",
                                    "status": "False",
                                    "reason": "ProgressDeadlineExceeded",
                                    "message": "ReplicaSet has timed out progressing.",
                                    "lastTransitionTime": "2021-01-01T00:00:00Z",
                                }
                            ],
                        },
                    }
                ]
            }
        if path.endswith("/statefulsets"):
            return {"items": []}
        raise AssertionError(f"unexpected path: {path}")


@pytest.mark.asyncio
async def test_rancher_find_stalled_rollouts_surfaces_reason_message_since_and_age_days() -> None:
    """M-B1/B2: a stalled rollout's ProgressDeadlineExceeded reason/message/
    since/ageDays reuse `deployments_list`'s own diagnosis helper (M-A7) — one
    definition of "why is this rollout stuck", not two."""

    result = await rancher_find_stalled_rollouts(
        namespace="default",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=_StalledRolloutConditionClient(),  # type: ignore[arg-type]
    )

    rollout = result.rollouts[0]
    assert rollout.reason == "ProgressDeadlineExceeded"
    assert rollout.message == "ReplicaSet has timed out progressing."
    assert rollout.since == "2021-01-01T00:00:00Z"
    assert rollout.age_days is not None and rollout.age_days > 1000


class _ConditionedPvcClient:
    """Stub with one PVC exposing a status.conditions[] entry — illustrative
    of a CSI-specific condition, not phase-derived — so reason/message/since/
    ageDays are checkable when the payload provides them."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        return {
            "items": [
                {
                    "metadata": {"name": "data", "namespace": "default"},
                    "spec": {
                        "storageClassName": "fast",
                        "resources": {"requests": {"storage": "50Gi"}},
                    },
                    "status": {
                        "phase": "Pending",
                        "conditions": [
                            {
                                "type": "Resizing",
                                "status": "False",
                                "reason": "ExternalExpanding",
                                "message": "waiting for an external controller",
                                "lastTransitionTime": "2021-01-01T00:00:00Z",
                            }
                        ],
                    },
                }
            ]
        }


@pytest.mark.asyncio
async def test_rancher_find_unbound_pvcs_surfaces_conditions_when_present() -> None:
    """M-B1/B2: reason/message/since/ageDays surface from a PVC's own
    status.conditions when the payload exposes them — a plain
    scheduling-stuck PVC commonly has none (that signal lives in Kubernetes
    Events, out of scope here), so absence must stay absence, not a guess."""

    result = await rancher_find_unbound_pvcs(
        namespace="default",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=_ConditionedPvcClient(),  # type: ignore[arg-type]
    )

    pvc = result.pvcs[0]
    assert pvc.reason == "ExternalExpanding"
    assert pvc.message == "waiting for an external controller"
    assert pvc.since == "2021-01-01T00:00:00Z"
    assert pvc.age_days is not None and pvc.age_days > 1000


class _BlockingPdbConditionClient:
    """Stub with one blocking PDB carrying a DisruptionAllowed=False condition."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        return {
            "items": [
                {
                    "metadata": {"name": "api-pdb", "namespace": "default"},
                    "spec": {"minAvailable": 1, "selector": {"matchLabels": {"app": "api"}}},
                    "status": {
                        "currentHealthy": 0,
                        "desiredHealthy": 1,
                        "disruptionsAllowed": 0,
                        "conditions": [
                            {
                                "type": "DisruptionAllowed",
                                "status": "False",
                                "reason": "InsufficientPods",
                                "message": "The disruption budget api-pdb needs 1 healthy pods",
                                "lastTransitionTime": "2021-01-01T00:00:00Z",
                            }
                        ],
                    },
                }
            ]
        }


@pytest.mark.asyncio
async def test_rancher_find_pdbs_blocking_surfaces_disruption_condition() -> None:
    """M-B1/B2: a blocking PDB's reason/message/since/ageDays come from its
    own DisruptionAllowed condition when the API server populates it
    (policy/v1; absent on older servers, so this stays optional)."""

    result = await rancher_find_pdbs_blocking(
        namespace="default",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=_BlockingPdbConditionClient(),  # type: ignore[arg-type]
    )

    blocker = result.blockers[0]
    assert blocker.reason == "InsufficientPods"
    assert blocker.message == "The disruption budget api-pdb needs 1 healthy pods"
    assert blocker.since == "2021-01-01T00:00:00Z"
    assert blocker.age_days is not None and blocker.age_days > 1000
