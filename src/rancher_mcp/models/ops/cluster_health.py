"""Typed models for cluster health convenience tools."""

from pydantic import Field, computed_field

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
    # Say-nothing when healthy (M-A10 / ADR-0002 rule #2): 0/0/[] collectively
    # say nothing, and a real unhealthy component already folds into `issues[]`
    # below (see `derive_cluster_issues`/`_component_issue_severity` in
    # `tools/support/cluster_issues.py`) with severity + message, so the
    # exception still surfaces without these three standalone counters. Stay
    # populated as attributes (`exclude=True` only affects serialization) so
    # existing attribute-asserting callers/tests are unaffected.
    component_healthy_count: int = Field(default=0, exclude=True)
    component_unhealthy_count: int = Field(default=0, exclude=True)
    component_unhealthy_names: list[str] = Field(
        default_factory=_empty_strings,
        exclude=True,
    )
    nodes: NodeHealthRollup = Field(default_factory=NodeHealthRollup)
    issues: list[ClusterIssue] = Field(default_factory=_empty_issues)


class ClusterHealthSummary(RancherModel):
    """Lightweight health summary for one cluster in a fleet rollup."""

    cluster_id: str
    cluster_name: str
    state: str | None = None
    healthy: bool
    # Collapsed into the `nodes` token below (M-A8 / ADR-0002 rule #3): three
    # separate ints said the same thing three different ways across a
    # multi-cluster list. Stay populated as attributes (`exclude=True` only
    # affects serialization) so existing attribute-asserting tests pass.
    node_count: int | None = Field(default=None, exclude=True)
    nodes_ready: int = Field(default=0, exclude=True)
    nodes_not_ready: int = Field(default=0, exclude=True)
    issue_count: int = 0
    top_issues: list[ClusterIssue] = Field(default_factory=_empty_issues)

    @computed_field
    @property
    def nodes(self) -> str:
        """Collapsed ready/total node token, e.g. ``"3/3"`` (M-A8 / ADR-0002
        rule #3 — "collapsed tokens ... nodes:'3/3'"). A quick glance already
        reads exception-shaped (``"1/3"`` signals trouble on its own); the
        `NodesNotReady`/`NodesUnschedulable` issue types carry the detail."""

        return f"{self.nodes_ready}/{self.nodes_ready + self.nodes_not_ready}"


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
