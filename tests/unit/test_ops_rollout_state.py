"""When is a rollout over? The rules, per controller kind.

These are ``kubectl rollout status``'s rules. Each test below is one way a
rollout can look finished while it is not, or look unfinished while there is
nothing left to wait for.
"""

from __future__ import annotations

from _rollout_support import daemonset_payload, deployment_payload, statefulset_payload

from rancher_mcp.tools.ops.rollout_state import read_rollout_state


def test_a_converged_deployment_is_complete() -> None:
    state = read_rollout_state("deployment", deployment_payload())

    assert state.complete
    assert (state.desired, state.updated, state.ready, state.available) == (3, 3, 3, 3)
    assert state.reason is None


def test_a_deployment_still_replacing_pods_is_not_complete() -> None:
    assert not read_rollout_state("deployment", deployment_payload(updated=1)).complete
    assert not read_rollout_state("deployment", deployment_payload(available=2)).complete


def test_old_pods_still_terminating_keep_a_rollout_open() -> None:
    """Every new pod can be available while the old ones are not gone yet."""

    assert not read_rollout_state("deployment", deployment_payload(total=5)).complete


def test_counts_from_before_the_change_do_not_count() -> None:
    """Until the controller has observed the new spec its status describes the
    previous rollout — which was, very likely, complete."""

    behind = deployment_payload(generation=5, observed=4)
    unseen = deployment_payload(generation=5, observed=None)

    assert not read_rollout_state("deployment", behind).complete
    assert not read_rollout_state("deployment", unseen).complete


def test_a_deployment_with_no_replica_count_wants_one() -> None:
    payload = deployment_payload(desired=None, updated=1, available=1)

    state = read_rollout_state("deployment", payload)

    assert state.desired == 1
    assert state.complete


def test_a_deployment_past_its_progress_deadline_has_failed() -> None:
    stuck = [
        {
            "type": "Progressing",
            "status": "False",
            "reason": "ProgressDeadlineExceeded",
            "message": 'ReplicaSet "web-7d9" has timed out progressing.',
        }
    ]
    payload = deployment_payload(updated=1, available=1, conditions=stuck)

    state = read_rollout_state("deployment", payload)

    assert state.failed
    assert state.reason == "ProgressDeadlineExceeded"
    assert "timed out progressing" in (state.message or "")


def test_a_paused_deployment_is_reported_as_paused() -> None:
    assert read_rollout_state("deployment", deployment_payload(updated=1, paused=True)).paused


def test_a_statefulset_is_complete_once_it_has_adopted_the_new_revision() -> None:
    def complete(**status: object) -> bool:
        return read_rollout_state("statefulset", statefulset_payload(**status)).complete

    assert complete()
    assert not complete(currentRevision="db-a")
    assert not complete(updatedReplicas=2)
    assert not complete(readyReplicas=2)


def test_a_statefulset_without_available_counts_falls_back_to_ready() -> None:
    assert read_rollout_state("statefulset", statefulset_payload()).available == 3


def test_a_partitioned_statefulset_only_has_to_update_above_the_partition() -> None:
    payload = statefulset_payload(updatedReplicas=1, currentRevision="db-a")
    payload["spec"] = {"replicas": 3, "updateStrategy": {"rollingUpdate": {"partition": 2}}}

    assert read_rollout_state("statefulset", payload).complete


def test_an_on_delete_workload_is_judged_on_readiness_and_says_why() -> None:
    payload = statefulset_payload(updatedReplicas=0, currentRevision="db-a")
    payload["spec"] = {"replicas": 3, "updateStrategy": {"type": "OnDelete"}}

    state = read_rollout_state("statefulset", payload)

    assert state.complete
    assert "OnDelete" in (state.message or "")


def test_a_daemonset_is_complete_when_every_node_runs_the_new_pod() -> None:
    def complete(**status: int) -> bool:
        return read_rollout_state("daemonset", daemonset_payload(**status)).complete

    assert complete()
    assert not complete(updatedNumberScheduled=3)
    assert not complete(numberAvailable=3)


def test_a_daemonset_with_no_nodes_to_run_on_has_nothing_to_wait_for() -> None:
    idle = daemonset_payload(
        desiredNumberScheduled=0, updatedNumberScheduled=0, numberReady=0, numberAvailable=0
    )

    assert read_rollout_state("daemonset", idle).complete
