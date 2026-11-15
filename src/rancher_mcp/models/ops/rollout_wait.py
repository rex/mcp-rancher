"""Typed result for following a workload rollout to its end."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from rancher_mcp.models.base import RancherModel

RolloutKind = Literal["deployment", "statefulset", "daemonset"]
RolloutOutcome = Literal["complete", "timed_out", "failed", "paused"]


class RolloutWaitResult(RancherModel):
    """Where a rollout stood when the wait ended, and why the wait ended.

    ``outcome`` is the field to branch on:

    * ``complete`` — every replica is on the new revision and available.
    * ``timed_out`` — still moving when the deadline passed. Not a verdict on
      the rollout: call again to keep waiting, or look at what is holding it.
    * ``failed`` — the controller itself has given up (a Deployment past its
      progress deadline). Waiting longer will not help.
    * ``paused`` — the Deployment is paused, so it will not move until resumed.

    The four counts are always present, including when they are zero, so a
    caller can report "3 of 5" without checking which keys exist.
    """

    instance: str
    cluster_id: str
    namespace: str
    resource_kind: str
    name: str
    outcome: str
    desired: int = Field(description="Replicas the workload is meant to run.")
    updated: int = Field(description="Replicas already on the new revision.")
    ready: int = Field(description="Replicas passing their readiness checks.")
    available: int = Field(description="Replicas ready for at least minReadySeconds.")
    generation: int | None = None
    observed_generation: int | None = Field(
        default=None,
        description="Lower than `generation` means the controller has not yet seen the change.",
    )
    reason: str | None = Field(
        default=None, description="Why the rollout is not complete, when the cluster says."
    )
    message: str | None = None
    waited_seconds: int = Field(description="How long this call waited.")
    polls: int = Field(description="How many times the workload was read.")
