"""Node diagnostics tests (ROADMAP L-2a / ADR-0002).

K-2 dropped requested/os/kernel/runtime with the raw payload; L-2a restores them
as always-on typed fields and derives human units + utilization. Fixtures use
Rancher's Norman node paths (requested.*, info.os.*).
"""

from __future__ import annotations

from rancher_mcp.models.clusters_nodes import (
    RancherNodeDetail,
    RancherNodeList,
    RancherNodeSummary,
)

_NODE = {
    "id": "c-x:m1",
    "name": "c-x:m1",
    "hostname": "kube-node-1",
    "capacity": {"cpu": "4", "memory": "4005204Ki", "pods": "110"},
    "requested": {"cpu": "1880m", "memory": "2522Mi"},
    "info": {
        "kubernetes": {"kubeletVersion": "v1.27.16+rke2r1"},
        "os": {
            "operatingSystem": "Ubuntu 22.04.2 LTS",
            "kernelVersion": "5.15.0-185-generic",
            "dockerVersion": "containerd://1.7.17-k3s1",
        },
    },
    "conditions": [
        {"type": "Ready", "status": "True"},
        {"type": "Registered", "status": "True"},
        {"type": "Ready", "status": "True"},  # Rancher emits Ready twice
    ],
}


def test_node_detail_restores_and_derives_diagnostics() -> None:
    dumped = RancherNodeDetail.model_validate(_NODE).model_dump(by_alias=True)
    # Restored (the K-2 over-trim fix):
    assert dumped["requestedCpu"] == "1880m"
    assert dumped["requestedMemory"] == "2522Mi"
    assert dumped["osImage"] == "Ubuntu 22.04.2 LTS"
    assert dumped["kernelVersion"] == "5.15.0-185-generic"
    assert dumped["containerRuntime"] == "containerd://1.7.17-k3s1"
    # Derived (ADR-0002 rule #3 — no arithmetic for the agent):
    assert dumped["memoryCapacityHuman"] == "3.8Gi"
    assert dumped["cpuUtilization"] == "47%"
    assert dumped["memoryUtilization"] == "64%"
    # Duplicate Ready condition deduped 3 -> 2.
    assert [c["type"] for c in dumped["conditions"]] == ["Ready", "Registered"]


def test_node_list_rolls_up_versions_for_the_upgrade_matrix() -> None:
    other = {**_NODE, "info": {"kubernetes": {"kubeletVersion": "v1.26.15+rke2r1"}}}
    node_list = RancherNodeList(
        instance="work",
        node_count=2,
        nodes=[RancherNodeSummary.model_validate(_NODE), RancherNodeSummary.model_validate(other)],
    )
    summary = node_list.model_dump(by_alias=True)["summary"]
    assert summary["versions"] == {"v1.27.16+rke2r1": 1, "v1.26.15+rke2r1": 1}
