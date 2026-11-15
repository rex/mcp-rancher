"""`rancher_rollout_wait`: the waiting, the tool, and what a client actually
receives while it waits. (The rules for *when* a rollout is over are in
``test_ops_rollout_state.py``.)

Nothing here sleeps for real. The loop takes its clock and its sleep as
arguments, so a five-minute wait is a list of numbers.
"""

from __future__ import annotations

from typing import Any

import pytest
from _rollout_support import FakeTime as _Time
from _rollout_support import ScriptedWorkload as _Workload
from _rollout_support import deployment_payload as _deployment
from mcp import Client
from mcp.server.mcpserver import MCPServer

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherNotFoundError
from rancher_mcp.tools.ops import register_ops_tools, rollout_wait
from rancher_mcp.tools.ops.rollout_state import RolloutState
from rancher_mcp.tools.ops.rollout_wait import rancher_rollout_wait, wait_for_rollout

# ── The waiting ─────────────────────────────────────────────────────────────


def _state(*, updated: int = 0, complete: bool = False, **extra: Any) -> RolloutState:
    return RolloutState(3, updated, updated, updated, 2, 2, complete, **extra)


async def _run(states: list[RolloutState], *, timeout: float = 300) -> dict[str, Any]:
    time = _Time()
    remaining = list(states)
    reported: list[str] = []

    async def read() -> RolloutState:
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    async def on_progress(state: RolloutState, waited: float) -> None:
        reported.append(f"{int(waited)}s {state.summary()}")

    state, outcome, waited, polls = await wait_for_rollout(
        read, timeout_seconds=timeout, on_progress=on_progress, sleep=time.sleep, clock=time.clock
    )
    return {
        "state": state,
        "outcome": outcome,
        "waited": waited,
        "polls": polls,
        "slept": time.slept,
        "reported": reported,
    }


async def test_a_rollout_that_is_already_over_costs_one_read_and_no_wait() -> None:
    run = await _run([_state(updated=3, complete=True)])

    assert run["outcome"] == "complete"
    assert run["polls"] == 1
    assert run["slept"] == []
    assert run["reported"] == []


async def test_it_reports_each_step_and_backs_off_while_it_waits() -> None:
    run = await _run(
        [_state(updated=0), _state(updated=1), _state(updated=2), _state(updated=3, complete=True)]
    )

    assert run["outcome"] == "complete"
    assert run["polls"] == 4
    assert run["slept"] == [2.0, 3.0, 4.5]
    assert run["reported"] == [
        "0s 0/3 updated, 0/3 available",
        "2s 1/3 updated, 1/3 available",
        "5s 2/3 updated, 2/3 available",
    ]


async def test_the_interval_stops_growing() -> None:
    run = await _run([_state(updated=1)], timeout=120)

    assert max(run["slept"]) == 10.0


async def test_it_gives_up_at_the_deadline_and_says_where_things_stood() -> None:
    run = await _run([_state(updated=1)], timeout=5)

    assert run["outcome"] == "timed_out"
    assert run["state"].updated == 1
    assert run["waited"] == 5
    assert run["slept"] == [2.0, 3.0], "the last sleep must stop at the deadline, not overshoot it"


@pytest.mark.parametrize(
    ("state", "outcome"),
    [(_state(failed=True), "failed"), (_state(paused=True), "paused")],
)
async def test_a_rollout_that_will_never_finish_is_not_waited_on(
    state: RolloutState, outcome: str
) -> None:
    run = await _run([state])

    assert run["outcome"] == outcome
    assert run["slept"] == []


# ── The tool ────────────────────────────────────────────────────────────────


def _settings() -> AppSettings:
    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":true}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


async def test_it_follows_a_rollout_to_completion() -> None:
    time = _Time()
    client = _Workload(_deployment(updated=1, available=1), _deployment())

    result = await rancher_rollout_wait(
        resource_kind="deployment",
        name="web",
        namespace="shop",
        cluster_id="c-m-abc",
        settings=_settings(),
        client=client,
        sleep=time.sleep,
        clock=time.clock,
    )

    assert (
        client.paths == ["/k8s/clusters/c-m-abc/apis/apps/v1/namespaces/shop/deployments/web"] * 2
    )
    assert result.outcome == "complete"
    assert (result.desired, result.updated, result.available) == (3, 3, 3)
    assert result.polls == 2
    assert result.waited_seconds == 2
    assert result.suggested_next_steps == []


async def test_a_wait_that_does_not_end_well_says_where_to_look() -> None:
    time = _Time()

    result = await rancher_rollout_wait(
        resource_kind="deployment",
        name="web",
        namespace="shop",
        timeout_seconds=4,
        settings=_settings(),
        client=_Workload(_deployment(updated=1, available=1)),
        sleep=time.sleep,
        clock=time.clock,
    )

    assert result.outcome == "timed_out"
    assert result.suggested_next_steps == [
        "rancher_find_failing_pods",
        "rancher_cluster_events_list",
    ]


async def test_a_workload_that_does_not_exist_is_an_error_not_a_wait() -> None:
    class Missing(_Workload):
        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            raise RancherNotFoundError(404, "deployments.apps web not found")

    with pytest.raises(RancherNotFoundError):
        await rancher_rollout_wait(
            resource_kind="deployment",
            name="web",
            namespace="shop",
            settings=_settings(),
            client=Missing(),
        )


# ── What a client receives ──────────────────────────────────────────────────


@pytest.mark.parametrize("era", ["legacy", "2026-07-28"])
async def test_a_client_is_told_how_the_rollout_is_going_while_it_waits(
    era: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    time = _Time()
    client = _Workload(
        _deployment(updated=1, available=0), _deployment(updated=2, available=2), _deployment()
    )
    follow = rollout_wait.rancher_rollout_wait

    async def scripted(**kwargs: Any) -> Any:
        return await follow(
            **kwargs, settings=_settings(), client=client, sleep=time.sleep, clock=time.clock
        )

    monkeypatch.setattr(rollout_wait, "rancher_rollout_wait", scripted)
    mcp = MCPServer(name="rollout-probe", instructions="probe")
    register_ops_tools(mcp)
    heard: list[tuple[float, float | None, str | None]] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        heard.append((progress, total, message))

    async with Client(mcp, mode=era) as session:
        result = await session.call_tool(
            "rancher_rollout_wait",
            {"resource_kind": "deployment", "name": "web", "namespace": "shop"},
            progress_callback=on_progress,
        )

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["outcome"] == "complete"
    assert heard == [
        (0, 300, "1/3 updated, 0/3 available"),
        (2, 300, "2/3 updated, 2/3 available"),
    ]
    assert [progress for progress, _, _ in heard] == sorted(progress for progress, _, _ in heard)


async def test_the_tool_publishes_its_limits() -> None:
    mcp = MCPServer(name="rollout-probe", instructions="probe")
    register_ops_tools(mcp)

    (tool,) = [tool for tool in await mcp.list_tools() if tool.name == "rancher_rollout_wait"]
    properties = tool.input_schema["properties"]

    assert tool.annotations is not None and tool.annotations.read_only_hint is True
    assert properties["resource_kind"]["enum"] == ["deployment", "statefulset", "daemonset"]
    assert properties["timeout_seconds"]["minimum"] == 1
    assert properties["timeout_seconds"]["maximum"] == 1800
    assert properties["timeout_seconds"]["default"] == 300
    assert tool.input_schema["required"] == ["resource_kind", "name", "namespace"]
    assert "ctx" not in properties
