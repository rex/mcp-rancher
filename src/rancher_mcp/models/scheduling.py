"""Typed models for curated Kubernetes scheduling reads.

PriorityClass (``scheduling.k8s.io/v1``) and RuntimeClass
(``node.k8s.io/v1``) — both cluster-scoped scheduling primitives.
Used by ops agents to understand pod priority preemption and
runtime-class to-node binding.
"""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_priority_class_summaries() -> list["RancherPriorityClassSummary"]:
    """Return a typed empty PriorityClass summary list."""

    return []


def _empty_runtime_class_summaries() -> list["RancherRuntimeClassSummary"]:
    """Return a typed empty RuntimeClass summary list."""

    return []


class RancherPriorityClassSummary(RancherModel):
    """Typed summary for one PriorityClass (scheduling.k8s.io/v1, cluster-scoped)."""

    name: str = Field(
        default="<unknown-priority-class>",
        validation_alias=AliasPath("metadata", "name"),
    )
    value: int | None = None
    global_default: bool | None = Field(
        default=None,
        validation_alias=AliasPath("globalDefault"),
    )
    preemption_policy: str | None = Field(
        default=None,
        validation_alias=AliasPath("preemptionPolicy"),
    )
    description: str | None = None


class RancherPriorityClassDetail(RancherPriorityClassSummary):
    """Typed detail for one PriorityClass."""

    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherPriorityClassList(RancherModel):
    """Typed list response for PriorityClasses (cluster-scoped)."""

    instance: str
    cluster_id: str
    priority_class_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    priority_classes: list[RancherPriorityClassSummary] = Field(
        default_factory=_empty_priority_class_summaries,
    )


class RancherRuntimeClassSummary(RancherModel):
    """Typed summary for one RuntimeClass (node.k8s.io/v1, cluster-scoped)."""

    name: str = Field(
        default="<unknown-runtime-class>",
        validation_alias=AliasPath("metadata", "name"),
    )
    handler: str | None = None
    overhead_pod_fixed_keys: list[str] = Field(default_factory=list)
    scheduling_node_selector_keys: list[str] = Field(default_factory=list)


class RancherRuntimeClassDetail(RancherRuntimeClassSummary):
    """Typed detail for one RuntimeClass."""

    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherRuntimeClassList(RancherModel):
    """Typed list response for RuntimeClasses (cluster-scoped)."""

    instance: str
    cluster_id: str
    runtime_class_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    runtime_classes: list[RancherRuntimeClassSummary] = Field(
        default_factory=_empty_runtime_class_summaries,
    )
