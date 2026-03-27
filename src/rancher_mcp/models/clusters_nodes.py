"""Typed models for curated Rancher cluster and node reads."""

from pydantic import BaseModel, Field


def _empty_cluster_summaries() -> list["RancherClusterSummary"]:
    """Return a typed empty cluster-summary list for Pydantic default factories."""

    return []


def _empty_node_summaries() -> list["RancherNodeSummary"]:
    """Return a typed empty node-summary list for Pydantic default factories."""

    return []


def _empty_conditions() -> list["RancherCondition"]:
    """Return a typed empty condition list for Pydantic default factories."""

    return []


def _empty_component_statuses() -> list["RancherClusterComponentStatus"]:
    """Return a typed empty component-status list for Pydantic default factories."""

    return []


class RancherCondition(BaseModel):
    """One Rancher or Kubernetes condition."""

    type: str
    status: str | None = None
    reason: str | None = None
    message: str | None = None


class RancherClusterComponentStatus(BaseModel):
    """One summarized cluster component status."""

    name: str
    healthy: bool | None = None
    message: str | None = None


class RancherClusterSummary(BaseModel):
    """Typed summary for one Rancher cluster."""

    id: str
    name: str
    display_name: str | None = None
    state: str | None = None
    ready: bool | None = None
    provider: str | None = None
    driver: str | None = None
    kubernetes_version: str | None = None
    node_count: int | None = None
    cpu_capacity: str | None = None
    memory_capacity: str | None = None
    condition_types_true: list[str] = Field(default_factory=list)


class RancherClusterDetail(RancherClusterSummary):
    """Typed detail for one Rancher cluster."""

    api_endpoint: str | None = None
    action_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(default_factory=_empty_conditions)
    component_statuses: list[RancherClusterComponentStatus] = Field(
        default_factory=_empty_component_statuses
    )
    payload: dict[str, object] = Field(default_factory=dict)


class RancherClusterList(BaseModel):
    """Typed list response for Rancher clusters."""

    instance: str
    cluster_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    clusters: list[RancherClusterSummary] = Field(default_factory=_empty_cluster_summaries)


class RancherNodeSummary(BaseModel):
    """Typed summary for one Rancher-managed node."""

    id: str
    name: str
    cluster_id: str | None = None
    hostname: str | None = None
    state: str | None = None
    ready: bool | None = None
    roles: list[str] = Field(default_factory=list)
    kubernetes_version: str | None = None
    internal_ip: str | None = None
    external_ip: str | None = None
    unschedulable: bool | None = None


class RancherNodeDetail(RancherNodeSummary):
    """Typed detail for one Rancher-managed node."""

    node_name: str | None = None
    provider_id: str | None = None
    pod_cidr: str | None = None
    cpu_capacity: str | None = None
    memory_capacity: str | None = None
    pod_capacity: str | None = None
    cpu_allocatable: str | None = None
    memory_allocatable: str | None = None
    pod_allocatable: str | None = None
    action_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(default_factory=_empty_conditions)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherNodeList(BaseModel):
    """Typed list response for Rancher nodes."""

    instance: str
    node_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    nodes: list[RancherNodeSummary] = Field(default_factory=_empty_node_summaries)
