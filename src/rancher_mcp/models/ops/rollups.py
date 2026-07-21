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
    """One-call namespace workload rollup.

    ``pods_succeeded`` (terminal Job/Completed pods) is counted separately
    from ``pods_running``/``pods_pending``/``pods_failed`` so a namespace
    whose Jobs have finished doesn't read as half-down (M-A4). All four
    buckets are derived from ``classify_pod_health`` in
    ``models/pods_services.py`` — the definitions shared with
    ``RancherPodList.summary`` (L-2c) and ``ProjectHealthSummary`` below.
    """

    instance: str
    cluster_id: str
    namespace: str
    pod_count: int = 0
    pods_running: int = 0
    pods_pending: int = 0
    pods_failed: int = 0
    pods_succeeded: int = 0
    workloads: WorkloadControllerCounts = Field(
        default_factory=WorkloadControllerCounts,
    )


class ProjectHealthSummary(RancherModel):
    """One-call project health overview.

    ``succeeded_pods`` (terminal Job/Completed pods) is counted separately
    from ``failing_pods`` so completed Jobs never drag a healthy project's
    reading down (M-A4) — see ``classify_pod_health`` in
    ``models/pods_services.py`` for the shared bucket definitions.
    """

    instance: str
    project_id: str
    project_name: str
    state: str | None = None
    cluster_id: str | None = None
    namespace_count: int = 0
    namespaces: list[str] = Field(default_factory=list)
    total_pods: int = 0
    failing_pods: int = 0
    succeeded_pods: int = 0
    total_workloads: int = 0
    unhealthy_workloads: int = 0
