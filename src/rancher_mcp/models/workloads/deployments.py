"""Deployment workload models."""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.workloads.common import (
    RancherCondition,
    RancherWorkloadContainerSummary,
    empty_conditions,
    empty_container_summaries,
)


def _empty_deployment_summaries() -> list["RancherDeploymentSummary"]:
    """Return a typed empty deployment-summary list for Pydantic default factories."""

    return []


class RancherDeploymentSummary(RancherModel):
    """Typed summary for one deployment."""

    id: str = ""
    name: str = Field(
        default="<unknown-deployment>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    desired_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "replicas"),
    )
    ready_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "readyReplicas"),
    )
    available_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "availableReplicas"),
    )
    updated_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "updatedReplicas"),
    )
    unavailable_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "unavailableReplicas"),
    )
    ready: bool | None = None
    rollout_complete: bool | None = None
    strategy_type: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "strategy", "type"),
    )
    paused: bool | None = Field(default=None, validation_alias=AliasPath("spec", "paused"))
    selector_match_labels: dict[str, str] = Field(
        default_factory=dict,
        validation_alias=AliasPath("spec", "selector", "matchLabels"),
    )
    container_images: list[str] = Field(default_factory=list)


class RancherDeploymentDetail(RancherDeploymentSummary):
    """Typed detail for one deployment."""

    revision: str | None = Field(
        default=None,
        validation_alias=AliasPath("metadata", "annotations", "deployment.kubernetes.io/revision"),
    )
    generation: int | None = Field(
        default=None,
        validation_alias=AliasPath("metadata", "generation"),
    )
    observed_generation: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "observedGeneration"),
    )
    service_account_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "template", "spec", "serviceAccountName"),
    )
    min_ready_seconds: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "minReadySeconds"),
    )
    annotation_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(
        default_factory=empty_conditions,
        validation_alias=AliasPath("status", "conditions"),
    )
    containers: list[RancherWorkloadContainerSummary] = Field(
        default_factory=empty_container_summaries,
        validation_alias=AliasPath("spec", "template", "spec", "containers"),
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
