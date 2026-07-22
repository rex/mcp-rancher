"""DaemonSet workload models."""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.workloads.common import (
    RancherCondition,
    RancherWorkloadContainerSummary,
    empty_conditions,
    empty_container_summaries,
)


def _empty_daemonset_summaries() -> list["RancherDaemonSetSummary"]:
    """Return a typed empty daemonset-summary list for Pydantic default factories."""

    return []


class RancherDaemonSetSummary(RancherModel):
    """Typed summary for one daemonset."""

    id: str = ""
    name: str = Field(
        default="<unknown-daemonset>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    desired_number_scheduled: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "desiredNumberScheduled"),
    )
    current_number_scheduled: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "currentNumberScheduled"),
    )
    number_ready: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "numberReady"),
    )
    number_available: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "numberAvailable"),
    )
    number_unavailable: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "numberUnavailable"),
    )
    updated_number_scheduled: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "updatedNumberScheduled"),
    )
    ready: bool | None = None
    strategy_type: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "updateStrategy", "type"),
    )
    selector_match_labels: dict[str, str] = Field(
        default_factory=dict,
        validation_alias=AliasPath("spec", "selector", "matchLabels"),
    )
    container_images: list[str] = Field(default_factory=list)


class RancherDaemonSetDetail(RancherDaemonSetSummary):
    """Typed detail for one daemonset."""

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


class RancherDaemonSetList(RancherModel):
    """Typed list response for daemonsets in one namespace."""

    instance: str
    cluster_id: str
    namespace: str | None
    daemonset_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    daemonsets: list[RancherDaemonSetSummary] = Field(default_factory=_empty_daemonset_summaries)
