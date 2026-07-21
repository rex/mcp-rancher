"""Typed models for cluster health convenience tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.clusters_nodes import ClusterIssue, RancherCondition


def _empty_conditions() -> list[RancherCondition]:
    return []


def _empty_strings() -> list[str]:
    return []


def _empty_cluster_summaries() -> list["ClusterHealthSummary"]:
    return []


class NodeHealthRollup(RancherModel):
    """Aggregate node health counts for one cluster."""

    total: int = 0
    ready: int = 0
    not_ready: int = 0
    unschedulable: int = 0


def _empty_issues() -> list[ClusterIssue]:
    return []


def _empty_counts() -> dict[str, int]:
    return {}


class ClusterHealthCheck(RancherModel):
    """One-call cluster health diagnosis."""

    instance: str
    cluster_id: str
    cluster_name: str
    state: str | None = None
    healthy: bool
    kubernetes_version: str | None = None
    provider: str | None = None
    conditions: list[RancherCondition] = Field(
        default_factory=_empty_conditions,
    )
    condition_counts: dict[str, int] = Field(default_factory=_empty_counts)
    condition_types_false: list[str] = Field(
        default_factory=_empty_strings,
    )
    component_healthy_count: int = 0
    component_unhealthy_count: int = 0
    component_unhealthy_names: list[str] = Field(
        default_factory=_empty_strings,
    )
    nodes: NodeHealthRollup = Field(default_factory=NodeHealthRollup)
    issues: list[ClusterIssue] = Field(default_factory=_empty_issues)


class ClusterHealthSummary(RancherModel):
    """Lightweight health summary for one cluster in a fleet rollup."""

    cluster_id: str
    cluster_name: str
    state: str | None = None
    healthy: bool
    node_count: int | None = None
    nodes_ready: int = 0
    nodes_not_ready: int = 0
    issue_count: int = 0
    top_issues: list[ClusterIssue] = Field(default_factory=_empty_issues)


class ClustersHealthSummary(RancherModel):
    """Estate-wide cluster health rollup."""

    instance: str
    total_clusters: int
    healthy_count: int
    unhealthy_count: int
    by_severity: dict[str, int] = Field(default_factory=_empty_counts)
    versions: dict[str, int] = Field(default_factory=_empty_counts)
    clusters: list[ClusterHealthSummary] = Field(
        default_factory=_empty_cluster_summaries,
    )
