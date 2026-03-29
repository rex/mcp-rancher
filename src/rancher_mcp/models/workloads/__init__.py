"""Typed models for curated Rancher workload-controller reads."""

from rancher_mcp.models.workloads.common import RancherWorkloadContainerSummary
from rancher_mcp.models.workloads.daemonsets import (
    RancherDaemonSetDetail,
    RancherDaemonSetList,
    RancherDaemonSetSummary,
)
from rancher_mcp.models.workloads.deployments import (
    RancherDeploymentDetail,
    RancherDeploymentList,
    RancherDeploymentSummary,
)
from rancher_mcp.models.workloads.statefulsets import (
    RancherStatefulSetDetail,
    RancherStatefulSetList,
    RancherStatefulSetSummary,
)

__all__ = [
    "RancherDaemonSetDetail",
    "RancherDaemonSetList",
    "RancherDaemonSetSummary",
    "RancherDeploymentDetail",
    "RancherDeploymentList",
    "RancherDeploymentSummary",
    "RancherStatefulSetDetail",
    "RancherStatefulSetList",
    "RancherStatefulSetSummary",
    "RancherWorkloadContainerSummary",
]
