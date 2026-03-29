"""Typed models for curated Rancher workload-controller reads."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.clusters_nodes import RancherCondition


def _empty_conditions() -> list[RancherCondition]:
    """Return a typed empty condition list for Pydantic default factories."""

    return []


def _empty_container_summaries() -> list["RancherWorkloadContainerSummary"]:
    """Return a typed empty workload-container list for Pydantic default factories."""

    return []


def _empty_deployment_summaries() -> list["RancherDeploymentSummary"]:
    """Return a typed empty deployment-summary list for Pydantic default factories."""

    return []


def _empty_daemonset_summaries() -> list["RancherDaemonSetSummary"]:
    """Return a typed empty daemonset-summary list for Pydantic default factories."""

    return []


def _empty_statefulset_summaries() -> list["RancherStatefulSetSummary"]:
    """Return a typed empty statefulset-summary list for Pydantic default factories."""

    return []


class RancherWorkloadContainerSummary(RancherModel):
    """Typed summary for one workload template container."""

    name: str
    image: str | None = None


class RancherDeploymentSummary(RancherModel):
    """Typed summary for one deployment."""

    id: str
    name: str
    namespace: str
    desired_replicas: int | None = None
    ready_replicas: int | None = None
    available_replicas: int | None = None
    updated_replicas: int | None = None
    unavailable_replicas: int | None = None
    ready: bool | None = None
    rollout_complete: bool | None = None
    strategy_type: str | None = None
    paused: bool | None = None
    selector_match_labels: dict[str, str] = Field(default_factory=dict)
    container_images: list[str] = Field(default_factory=list)


class RancherDeploymentDetail(RancherDeploymentSummary):
    """Typed detail for one deployment."""

    revision: str | None = None
    generation: int | None = None
    observed_generation: int | None = None
    service_account_name: str | None = None
    min_ready_seconds: int | None = None
    annotation_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(default_factory=_empty_conditions)
    containers: list[RancherWorkloadContainerSummary] = Field(
        default_factory=_empty_container_summaries
    )
    payload: dict[str, object] = Field(default_factory=dict)


class RancherDeploymentList(RancherModel):
    """Typed list response for deployments in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    deployment_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    deployments: list[RancherDeploymentSummary] = Field(default_factory=_empty_deployment_summaries)


class RancherDaemonSetSummary(RancherModel):
    """Typed summary for one daemonset."""

    id: str
    name: str
    namespace: str
    desired_number_scheduled: int | None = None
    current_number_scheduled: int | None = None
    number_ready: int | None = None
    number_available: int | None = None
    number_unavailable: int | None = None
    updated_number_scheduled: int | None = None
    ready: bool | None = None
    strategy_type: str | None = None
    selector_match_labels: dict[str, str] = Field(default_factory=dict)
    container_images: list[str] = Field(default_factory=list)


class RancherDaemonSetDetail(RancherDaemonSetSummary):
    """Typed detail for one daemonset."""

    generation: int | None = None
    observed_generation: int | None = None
    service_account_name: str | None = None
    annotation_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(default_factory=_empty_conditions)
    containers: list[RancherWorkloadContainerSummary] = Field(
        default_factory=_empty_container_summaries
    )
    payload: dict[str, object] = Field(default_factory=dict)


class RancherDaemonSetList(RancherModel):
    """Typed list response for daemonsets in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    daemonset_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    daemonsets: list[RancherDaemonSetSummary] = Field(default_factory=_empty_daemonset_summaries)


class RancherStatefulSetSummary(RancherModel):
    """Typed summary for one statefulset."""

    id: str
    name: str
    namespace: str
    replicas: int | None = None
    ready_replicas: int | None = None
    current_replicas: int | None = None
    updated_replicas: int | None = None
    available_replicas: int | None = None
    ready: bool | None = None
    service_name: str | None = None
    update_strategy_type: str | None = None
    selector_match_labels: dict[str, str] = Field(default_factory=dict)
    container_images: list[str] = Field(default_factory=list)


class RancherStatefulSetDetail(RancherStatefulSetSummary):
    """Typed detail for one statefulset."""

    generation: int | None = None
    observed_generation: int | None = None
    current_revision: str | None = None
    update_revision: str | None = None
    service_account_name: str | None = None
    annotation_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(default_factory=_empty_conditions)
    containers: list[RancherWorkloadContainerSummary] = Field(
        default_factory=_empty_container_summaries
    )
    payload: dict[str, object] = Field(default_factory=dict)


class RancherStatefulSetList(RancherModel):
    """Typed list response for statefulsets in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    statefulset_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    statefulsets: list[RancherStatefulSetSummary] = Field(
        default_factory=_empty_statefulset_summaries
    )
