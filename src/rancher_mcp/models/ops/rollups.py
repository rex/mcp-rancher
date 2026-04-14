"""Typed models for namespace and project rollup convenience tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel


class WorkloadControllerCounts(RancherModel):
    """Aggregate workload controller counts."""

    deployments_total: int = 0
    deployments_ready: int = 0
    deployments_not_ready: int = 0
    daemonsets_total: int = 0
    daemonsets_ready: int = 0
    daemonsets_not_ready: int = 0
    statefulsets_total: int = 0
    statefulsets_ready: int = 0
    statefulsets_not_ready: int = 0


class NamespaceWorkloadsSummary(RancherModel):
    """One-call namespace workload rollup."""

    instance: str
    cluster_id: str
    namespace: str
    pod_count: int = 0
    pods_running: int = 0
    pods_pending: int = 0
    pods_failed: int = 0
    workloads: WorkloadControllerCounts = Field(
        default_factory=WorkloadControllerCounts,
    )


class ProjectHealthSummary(RancherModel):
    """One-call project health overview."""

    instance: str
    project_id: str
    project_name: str
    state: str | None = None
    cluster_id: str | None = None
    namespace_count: int = 0
    namespaces: list[str] = Field(default_factory=list)
    total_pods: int = 0
    failing_pods: int = 0
    total_workloads: int = 0
    unhealthy_workloads: int = 0
