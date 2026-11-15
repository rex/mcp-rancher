"""Shared pieces for the rollout tests: workload payloads as a Kubernetes API
would return them, a clock that never really waits, and a fake backend."""

from __future__ import annotations

from typing import Any


class FakeTime:
    """A clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


class ScriptedWorkload:
    """A backend that serves a scripted sequence of readings of one workload,
    repeating the last one for as long as it is asked."""

    def __init__(self, *readings: dict[str, object]) -> None:
        self._readings = list(readings)
        self.paths: list[str] = []

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        self.paths.append(path)
        return self._readings.pop(0) if len(self._readings) > 1 else self._readings[0]

    async def get_text(self, path: str, params: object = None) -> str:
        raise AssertionError("not used")

    async def post_json(self, path: str, payload: object = None, params: object = None) -> Any:
        raise AssertionError("a read-only tool tried to write")


def deployment_payload(
    *,
    desired: int | None = 3,
    updated: int = 3,
    available: int = 3,
    total: int | None = None,
    generation: int = 4,
    observed: int | None = 4,
    paused: bool = False,
    conditions: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    """A Deployment; with no arguments, one whose rollout is over."""

    spec: dict[str, object] = {"paused": paused}
    if desired is not None:
        spec["replicas"] = desired
    return {
        "metadata": {"name": "web", "generation": generation},
        "spec": spec,
        "status": {
            "replicas": updated if total is None else total,
            "updatedReplicas": updated,
            "readyReplicas": available,
            "availableReplicas": available,
            "observedGeneration": observed,
            "conditions": conditions or [],
        },
    }


def statefulset_payload(**status: object) -> dict[str, object]:
    """A three-replica StatefulSet on its new revision, with *status* overrides."""

    base: dict[str, object] = {
        "observedGeneration": 2,
        "readyReplicas": 3,
        "updatedReplicas": 3,
        "currentRevision": "db-b",
        "updateRevision": "db-b",
    }
    return {"metadata": {"generation": 2}, "spec": {"replicas": 3}, "status": base | status}


def daemonset_payload(**status: int) -> dict[str, object]:
    """A DaemonSet running its new pod on all four nodes, with *status* overrides."""

    base = {
        "observedGeneration": 1,
        "desiredNumberScheduled": 4,
        "updatedNumberScheduled": 4,
        "numberReady": 4,
        "numberAvailable": 4,
    }
    return {"metadata": {"generation": 1}, "spec": {}, "status": base | status}
