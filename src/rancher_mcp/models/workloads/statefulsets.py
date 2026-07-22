"""StatefulSet workload models."""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.workloads.common import (
    RancherCondition,
    RancherWorkloadContainerSummary,
    empty_conditions,
    empty_container_summaries,
)


def _empty_statefulset_summaries() -> list["RancherStatefulSetSummary"]:
    """Return a typed empty statefulset-summary list for Pydantic default factories."""

    return []


class RancherStatefulSetSummary(RancherModel):
    """Typed summary for one statefulset."""

    id: str = ""
    name: str = Field(
        default="<unknown-statefulset>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "replicas"),
    )
    ready_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "readyReplicas"),
    )
    current_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "currentReplicas"),
    )
    updated_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "updatedReplicas"),
    )
    available_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "availableReplicas"),
    )
    ready: bool | None = None
    service_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "serviceName"),
    )
    update_strategy_type: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "updateStrategy", "type"),
    )
    selector_match_labels: dict[str, str] = Field(
        default_factory=dict,
        validation_alias=AliasPath("spec", "selector", "matchLabels"),
    )
    container_images: list[str] = Field(default_factory=list)


class RancherStatefulSetDetail(RancherStatefulSetSummary):
    """Typed detail for one statefulset."""

    generation: int | None = Field(
        default=None,
        validation_alias=AliasPath("metadata", "generation"),
    )
    observed_generation: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "observedGeneration"),
    )
    current_revision: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "currentRevision"),
    )
    update_revision: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "updateRevision"),
    )
    service_account_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "template", "spec", "serviceAccountName"),
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


class RancherStatefulSetList(RancherModel):
    """Typed list response for statefulsets in one namespace."""

    instance: str
    cluster_id: str
    namespace: str | None
    statefulset_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    statefulsets: list[RancherStatefulSetSummary] = Field(
        default_factory=_empty_statefulset_summaries
    )
