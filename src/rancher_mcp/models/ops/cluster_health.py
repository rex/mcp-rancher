"""Typed models for cluster health convenience tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.clusters_nodes import RancherCondition


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
    condition_types_true: list[str] = Field(
        default_factory=_empty_strings,
    )
    condition_types_false: list[str] = Field(
        default_factory=_empty_strings,
    )
    component_healthy_count: int = 0
    component_unhealthy_count: int = 0
    component_unhealthy_names: list[str] = Field(
        default_factory=_empty_strings,
    )
    nodes: NodeHealthRollup = Field(default_factory=NodeHealthRollup)
    issues: list[str] = Field(default_factory=_empty_strings)


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
    top_issues: list[str] = Field(default_factory=_empty_strings)


class ClustersHealthSummary(RancherModel):
    """Estate-wide cluster health rollup."""

    instance: str
    total_clusters: int
    healthy_count: int
    unhealthy_count: int
    clusters: list[ClusterHealthSummary] = Field(
        default_factory=_empty_cluster_summaries,
    )
