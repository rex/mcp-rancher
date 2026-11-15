"""Reduce one workload object to the facts that decide whether its rollout is over.

The rules are ``kubectl rollout status``'s, per controller kind. They are kept
apart from the waiting (``rollout_wait.py``) because they are pure — a payload
in, a verdict out — and because a task that outlives this process has to be
able to re-derive the same verdict from a fresh read.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from rancher_mcp.tools.support.conditions import conditions_from_value
from rancher_mcp.tools.support.values import bool_value, int_value, mapping_value, string_value
from rancher_mcp.tools.workloads.shared import deployment_rollout_diagnosis

_ON_DELETE_NOTE = (
    "updateStrategy is OnDelete: pods move to the new revision only when something "
    "deletes them, so `updated` may never reach `desired` on its own."
)


@dataclass(frozen=True)
class RolloutState:
    """One reading of a workload, reduced to what decides a rollout."""

    desired: int
    updated: int
    ready: int
    available: int
    generation: int | None
    observed_generation: int | None
    complete: bool
    paused: bool = False
    failed: bool = False
    reason: str | None = None
    message: str | None = None

    def summary(self) -> str:
        """The line a person watching would want: how far along it is."""

        return f"{self.updated}/{self.desired} updated, {self.available}/{self.desired} available"


def _count(payload: Mapping[str, object], key: str) -> int:
    return int_value(payload, key) or 0


def _controller_has_seen(generation: int | None, observed: int | None) -> bool:
    """False while the controller is still acting on an older spec — its counts
    then describe the rollout before this one, however complete they look."""

    return generation is None or (observed is not None and observed >= generation)


def read_rollout_state(resource_kind: str, payload: Mapping[str, object]) -> RolloutState:
    """Reduce one deployment, statefulset or daemonset to its rollout state."""

    metadata = mapping_value(payload, "metadata") or {}
    spec = mapping_value(payload, "spec") or {}
    status = mapping_value(payload, "status") or {}
    generation = int_value(metadata, "generation")
    observed = int_value(status, "observedGeneration")
    seen = _controller_has_seen(generation, observed)
    strategy = mapping_value(spec, "updateStrategy") or {}
    on_delete = string_value(strategy, "type") == "OnDelete"
    note = _ON_DELETE_NOTE if on_delete else None

    if resource_kind == "daemonset":
        desired = _count(status, "desiredNumberScheduled")
        updated = _count(status, "updatedNumberScheduled")
        available = _count(status, "numberAvailable")
        complete = seen and available >= desired and (on_delete or updated >= desired)
        ready = _count(status, "numberReady")
        return RolloutState(
            desired, updated, ready, available, generation, observed, complete, message=note
        )

    replicas = int_value(spec, "replicas")
    desired = 1 if replicas is None else replicas
    updated = _count(status, "updatedReplicas")
    ready = _count(status, "readyReplicas")

    if resource_kind == "statefulset":
        reported = int_value(status, "availableReplicas")
        available = ready if reported is None else reported
        partition = _count(mapping_value(strategy, "rollingUpdate") or {}, "partition")
        current = string_value(status, "currentRevision")
        target = string_value(status, "updateRevision")
        # With a partition the two revisions are meant to differ; otherwise the
        # rollout is over only once the controller has adopted the new one.
        settled = partition > 0 or current is None or target is None or current == target
        rolled = on_delete or (updated >= max(desired - partition, 0) and settled)
        complete = seen and ready >= desired and rolled
        return RolloutState(
            desired, updated, ready, available, generation, observed, complete, message=note
        )

    available = _count(status, "availableReplicas")
    reason, message, _since = deployment_rollout_diagnosis(
        conditions_from_value(status.get("conditions"))
    )
    # `status.replicas` above `updatedReplicas` means old pods are still being
    # terminated: every new one can be available and the rollout is not over.
    no_old_pods = _count(status, "replicas") <= updated
    complete = seen and updated >= desired and no_old_pods and available >= desired
    return RolloutState(
        desired,
        updated,
        ready,
        available,
        generation,
        observed,
        complete,
        paused=bool_value(spec, "paused") is True,
        failed=reason == "ProgressDeadlineExceeded",
        reason=None if complete else reason,
        message=None if complete else message,
    )
