"""Curated Deployment response-shaping tests (M-A7 replicas token + reason/since).

Split from ``test_workloads_deployments_tools.py`` to stay under the
architecture line limit — that module keeps the baseline list/get + set_
annotations tests; this one owns the ADR-0002 rule #2/#3/#4 shaping behavior
added in M-A7: the collapsed ``replicas:"ready/desired"`` token and the
not-converged ``reason``/``since`` promotion, for both ``deployments_list``
and ``deployment_get``.
"""

from __future__ import annotations

import pytest
from _workloads_support import (
    StubRawK8sClient,
    build_settings,
)

from rancher_mcp.tools.workloads import (
    rancher_deployment_get,
    rancher_deployments_list,
)


@pytest.mark.asyncio
async def test_rancher_deployments_list_collapses_replicas_token_when_converged() -> None:
    """M-A7: a converged deployment renders a `replicas:"2/2"` token with no
    `reason`/`since` and none of the five raw replica ints in the dump — they
    stay real attributes (exclude=True is dump-only), just not in the shape
    an agent sees by default (ADR-0002 rules #2/#3)."""

    result = await rancher_deployments_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        ready=True,
        limit=5,
        label_selector="app=cattle-cluster-agent",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    deployment = result.deployments[0]
    assert deployment.replicas == "2/2"
    assert deployment.reason is None
    assert deployment.message is None  # M-B1/B2
    assert deployment.since is None
    assert deployment.age_days is None  # M-B1/B2: no `since` to derive from
    # Attributes still populate internally — exclude=True is dump-only.
    assert deployment.desired_replicas == 2
    assert deployment.ready_replicas == 2
    assert deployment.available_replicas == 2
    assert deployment.updated_replicas == 2

    dumped = result.model_dump(by_alias=True)["deployments"][0]
    assert dumped["replicas"] == "2/2"
    assert "reason" not in dumped
    assert "message" not in dumped
    assert "since" not in dumped
    assert "ageDays" not in dumped
    assert "desiredReplicas" not in dumped
    assert "readyReplicas" not in dumped
    assert "availableReplicas" not in dumped
    assert "updatedReplicas" not in dumped
    assert "unavailableReplicas" not in dumped


@pytest.mark.asyncio
async def test_rancher_deployment_get_collapses_replicas_token_when_converged() -> None:
    """M-A7: `deployment_get`'s codegen'd copy path (`summary_copy_fields`)
    carries the same converged-state collapse as `deployments_list`."""

    result = await rancher_deployment_get(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.replicas == "2/2"
    assert result.reason is None
    assert result.since is None

    dumped = result.model_dump(by_alias=True)
    assert dumped["replicas"] == "2/2"
    assert "reason" not in dumped
    assert "since" not in dumped
    assert "desiredReplicas" not in dumped
    assert "readyReplicas" not in dumped
    assert "availableReplicas" not in dumped
    assert "updatedReplicas" not in dumped
    assert "unavailableReplicas" not in dumped


class StalledRolloutClient:
    """Deterministic raw K8s client for a not-converged deployment.

    `readyReplicas` (1) trails `spec.replicas` (3) and the `Progressing`
    condition is `False` with reason ``ProgressDeadlineExceeded`` — the
    canonical stalled-rollout signal (M-A7).
    """

    _COLLECTION = "/k8s/clusters/venue-local/apis/apps/v1/namespaces/cattle-system/deployments"
    _PAYLOAD: dict[str, object] = {
        "metadata": {
            "name": "stuck-deployment",
            "namespace": "cattle-system",
            "generation": 5,
        },
        "spec": {
            "replicas": 3,
            "selector": {"matchLabels": {"app": "stuck"}},
            "template": {"spec": {"containers": [{"name": "app", "image": "demo:v2"}]}},
        },
        "status": {
            "observedGeneration": 5,
            "readyReplicas": 1,
            "availableReplicas": 1,
            "updatedReplicas": 1,
            "conditions": [
                {
                    "type": "Progressing",
                    "status": "False",
                    "reason": "ProgressDeadlineExceeded",
                    "message": "ReplicaSet has timed out progressing.",
                    "lastTransitionTime": "2026-07-01T00:00:00Z",
                }
            ],
        },
    }

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Serve the same stalled deployment from both the collection and item paths."""

        if path == self._COLLECTION:
            return {"items": [self._PAYLOAD]}
        if path == f"{self._COLLECTION}/stuck-deployment":
            return dict(self._PAYLOAD)
        raise AssertionError(f"unexpected raw K8s path: {path}")


@pytest.mark.asyncio
async def test_rancher_deployments_list_surfaces_reason_and_since_when_rollout_stalled() -> None:
    """M-A7: ready<desired with a ProgressDeadlineExceeded condition promotes
    `reason`+`since` to the top level of the list item (ADR-0002 rules #2/#4)
    — no second call is needed to learn why the rollout is stuck."""

    result = await rancher_deployments_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StalledRolloutClient(),
    )

    deployment = result.deployments[0]
    assert deployment.replicas == "1/3"
    assert deployment.reason == "ProgressDeadlineExceeded"
    assert deployment.message == "ReplicaSet has timed out progressing."  # M-B1/B2
    assert deployment.since == "2026-07-01T00:00:00Z"
    assert deployment.age_days is not None and deployment.age_days > 0  # M-B1/B2
    assert deployment.ready is False

    dumped = result.model_dump(by_alias=True)["deployments"][0]
    assert dumped["replicas"] == "1/3"
    assert dumped["reason"] == "ProgressDeadlineExceeded"
    assert dumped["message"] == "ReplicaSet has timed out progressing."
    assert dumped["since"] == "2026-07-01T00:00:00Z"
    assert dumped["ageDays"] > 0
    assert "desiredReplicas" not in dumped
    assert "readyReplicas" not in dumped


@pytest.mark.asyncio
async def test_rancher_deployment_get_surfaces_reason_and_since_when_rollout_stalled() -> None:
    """M-A7: the codegen'd get flow copies `reason`/`since` from the summary
    onto the detail via `summary_copy_fields`, so `deployment_get` matches
    `deployments_list` for a stalled rollout."""

    result = await rancher_deployment_get(
        namespace="cattle-system",
        deployment_name="stuck-deployment",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StalledRolloutClient(),
    )

    assert result.replicas == "1/3"
    assert result.reason == "ProgressDeadlineExceeded"
    assert result.since == "2026-07-01T00:00:00Z"

    dumped = result.model_dump(by_alias=True)
    assert dumped["replicas"] == "1/3"
    assert dumped["reason"] == "ProgressDeadlineExceeded"
    assert dumped["since"] == "2026-07-01T00:00:00Z"
    assert "desiredReplicas" not in dumped
