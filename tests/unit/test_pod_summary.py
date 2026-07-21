"""pods_list phase-summary tests (ROADMAP L-2c / ADR-0002).

A namespace whose Completed migration Jobs sit beside live pods must not read as
half-down. The list ``summary`` separates succeeded (terminal) from running
health and exposes an ``unhealthy`` count the agent branches on.
"""

from __future__ import annotations

from rancher_mcp.models.pods_services import RancherPodList, RancherPodSummary


def _pod(phase: str, *, ready: bool = True) -> RancherPodSummary:
    pod = RancherPodSummary.model_validate({"metadata": {"name": "p"}, "status": {"phase": phase}})
    return pod.model_copy(update={"ready": ready})


def _summary(pods: list[RancherPodSummary]) -> dict[str, int]:
    pod_list = RancherPodList(
        instance="w", cluster_id="c", namespace="kong", pod_count=len(pods), pods=pods
    )
    return pod_list.model_dump(by_alias=True)["summary"]


def test_completed_jobs_do_not_read_as_half_down() -> None:
    pods = [_pod("Running") for _ in range(3)] + [_pod("Succeeded", ready=False) for _ in range(3)]
    assert _summary(pods) == {
        "running": 3,
        "succeeded": 3,
        "pending": 0,
        "failed": 0,
        "unhealthy": 0,
    }


def test_running_but_not_ready_counts_as_unhealthy() -> None:
    summary = _summary([_pod("Running", ready=False)])
    assert summary["unhealthy"] == 1
    assert summary["running"] == 0
