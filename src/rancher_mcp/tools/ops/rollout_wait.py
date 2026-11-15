"""Follow one workload's rollout until it finishes, fails or runs out of time.

After a restart, a scale or an image change the only way to learn how it went
used to be to ask again, and again: a model polling ``deployment_get`` in a
loop, paying for the whole response each time and deciding for itself when to
give up. This tool does the waiting in one call. It reads the workload on a
backing-off interval, reports progress as it goes — which a client can show,
and which keeps the call from being dropped as idle — and returns once, with a
verdict.

A rollout that will never finish is not waited on: a Deployment past its
progress deadline is ``failed`` at once, and a paused one is ``paused`` at once.

Read-only: it sends nothing but ``GET``.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

import anyio
from mcp.server.mcpserver import Context
from pydantic import Field

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.ops.rollout_wait import RolloutKind, RolloutOutcome, RolloutWaitResult
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.ops.rollout_state import RolloutState, read_rollout_state
from rancher_mcp.tools.workloads.paths import workload_resource_path

_RESOURCES: dict[str, str] = {
    "deployment": "deployments",
    "statefulset": "statefulsets",
    "daemonset": "daemonsets",
}

DEFAULT_TIMEOUT_SECONDS = 300
# Half an hour: a stdio call with neither a response nor progress for that long
# is abandoned by the client anyway, so a longer wait could never be collected.
MAX_TIMEOUT_SECONDS = 1800
_FIRST_INTERVAL_SECONDS = 2.0
_MAX_INTERVAL_SECONDS = 10.0
_WHEN_NOT_COMPLETE = ["rancher_find_failing_pods", "rancher_cluster_events_list"]

Sleep = Callable[[float], Awaitable[None]]
Clock = Callable[[], float]
ProgressReport = Callable[[RolloutState, float], Awaitable[None]]


async def wait_for_rollout(
    read: Callable[[], Awaitable[RolloutState]],
    *,
    timeout_seconds: float,
    on_progress: ProgressReport,
    sleep: Sleep = anyio.sleep,
    clock: Clock = time.monotonic,
) -> tuple[RolloutState, RolloutOutcome, float, int]:
    """Read until the rollout ends one way or another.

    Returns the last reading, the verdict, the seconds waited and the number
    of reads. Always reads at least once, so a rollout that is already over is
    reported without any waiting at all.
    """

    started = clock()
    interval = _FIRST_INTERVAL_SECONDS
    polls = 0
    while True:
        state = await read()
        polls += 1
        waited = clock() - started
        if state.paused:
            return state, "paused", waited, polls
        if state.failed:
            return state, "failed", waited, polls
        if state.complete:
            return state, "complete", waited, polls
        if waited >= timeout_seconds:
            return state, "timed_out", waited, polls
        await on_progress(state, waited)
        await sleep(min(interval, timeout_seconds - waited))
        interval = min(interval * 1.5, _MAX_INTERVAL_SECONDS)


async def _follow(
    instance_name: str,
    resource_kind: str,
    name: str,
    namespace: str,
    cluster_id: str,
    timeout_seconds: int,
    client: ManagementDiscoveryClient,
    ctx: Context[Any, Any] | None,
    sleep: Sleep,
    clock: Clock,
) -> RolloutWaitResult:
    path = workload_resource_path(cluster_id, namespace, _RESOURCES[resource_kind], name)

    async def read() -> RolloutState:
        return read_rollout_state(resource_kind, await client.get_json(path))

    async def report(state: RolloutState, waited: float) -> None:
        if ctx is None:
            return
        try:
            # Elapsed time, not a replica count: the protocol requires progress
            # to only ever increase, and replicas go down as well as up.
            await ctx.report_progress(int(waited), timeout_seconds, state.summary())
        except ValueError:
            return  # not inside a request, so there is nobody to tell

    state, outcome, waited, polls = await wait_for_rollout(
        read, timeout_seconds=timeout_seconds, on_progress=report, sleep=sleep, clock=clock
    )
    return RolloutWaitResult(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        resource_kind=resource_kind,
        name=name,
        outcome=outcome,
        desired=state.desired,
        updated=state.updated,
        ready=state.ready,
        available=state.available,
        generation=state.generation,
        observed_generation=state.observed_generation,
        reason=state.reason,
        message=state.message,
        waited_seconds=int(waited),
        polls=polls,
        suggested_next_steps=[] if outcome == "complete" else list(_WHEN_NOT_COMPLETE),
    )


async def rancher_rollout_wait(
    resource_kind: str,
    name: str,
    namespace: str,
    cluster_id: str = "local",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
    ctx: Context[Any, Any] | None = None,
    sleep: Sleep = anyio.sleep,
    clock: Clock = time.monotonic,
) -> RolloutWaitResult:
    """Wait for one deployment, statefulset or daemonset rollout to end."""

    instance_name, instance_config = resolve_instance(settings or get_settings(), instance)
    target = (instance_name, resource_kind, name, namespace, cluster_id, timeout_seconds)
    if client is not None:
        return await _follow(*target, client, ctx, sleep, clock)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _follow(*target, managed_client, ctx, sleep, clock)


async def rancher_rollout_wait_tool(
    resource_kind: RolloutKind,
    name: str,
    namespace: str,
    cluster_id: str = "local",
    timeout_seconds: Annotated[int, Field(ge=1, le=MAX_TIMEOUT_SECONDS)] = DEFAULT_TIMEOUT_SECONDS,
    instance: str | None = None,
    ctx: Context[Any, Any] | None = None,
) -> RolloutWaitResult:
    """Wait for a deployment, statefulset or daemonset rollout to finish, and
    return once with the verdict — instead of polling a get tool in a loop.

    Call it after a restart, scale or image change. `outcome` is `complete`,
    `timed_out` (still moving when `timeout_seconds` ran out — call again to
    keep waiting), `failed` (the controller gave up; waiting will not help) or
    `paused`. Always returns the desired/updated/ready/available counts, and
    reports progress while it waits. Read-only.
    """

    return await rancher_rollout_wait(
        resource_kind=resource_kind,
        name=name,
        namespace=namespace,
        cluster_id=cluster_id,
        timeout_seconds=timeout_seconds,
        instance=instance,
        ctx=ctx,
    )
