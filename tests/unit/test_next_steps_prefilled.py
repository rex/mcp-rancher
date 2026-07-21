"""Pre-filled next-steps tests (ROADMAP L-3b / ADR-0002 Decision Outcome §2).

L-0 deleted the old bare ``suggestedNextSteps`` string array; L-3b re-adds it
*correctly* as a root-level ``{tool, args}`` — the tool names the model already
declares, each pre-filled with the scope args the agent lacks (cluster_id /
namespace), derived generically from the model's own fields.
"""

from __future__ import annotations

from rancher_mcp.models.ops.cluster_health import ClusterHealthCheck
from rancher_mcp.models.pods_services import RancherPodList


def test_next_steps_are_prefilled_with_cluster_scope() -> None:
    dumped = ClusterHealthCheck(
        instance="w",
        cluster_id="c-x",
        cluster_name="n",
        healthy=True,
        suggested_next_steps=["rancher_nodes_list"],
    ).model_dump(by_alias=True)
    assert dumped["nextSteps"] == [{"tool": "rancher_nodes_list", "args": {"cluster_id": "c-x"}}]
    assert "suggestedNextSteps" not in dumped  # the bare array is gone (L-0)


def test_next_steps_carry_namespace_scope_when_present() -> None:
    dumped = RancherPodList(
        instance="w",
        cluster_id="c-x",
        namespace="kong",
        pod_count=0,
        suggested_next_steps=["rancher_pod_get"],
    ).model_dump(by_alias=True)
    assert dumped["nextSteps"] == [
        {"tool": "rancher_pod_get", "args": {"cluster_id": "c-x", "namespace": "kong"}}
    ]


def test_no_next_steps_when_none_declared() -> None:
    dumped = ClusterHealthCheck(
        instance="w", cluster_id="c-x", cluster_name="n", healthy=True
    ).model_dump(by_alias=True)
    assert "nextSteps" not in dumped  # empty → dropped by the envelope
