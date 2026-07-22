"""Typed models for cluster-governance reads.

HorizontalPodAutoscaler (autoscaling/v2), ResourceQuota and
LimitRange (both core/v1) — the cluster-governance and
capacity-planning primitives that ops agents reach for when
debugging scaling and quota problems.
"""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_hpa_summaries() -> list["RancherHorizontalPodAutoscalerSummary"]:
    """Return a typed empty HPA summary list."""

    return []


def _empty_resource_quota_summaries() -> list["RancherResourceQuotaSummary"]:
    """Return a typed empty ResourceQuota summary list."""

    return []


def _empty_limit_range_summaries() -> list["RancherLimitRangeSummary"]:
    """Return a typed empty LimitRange summary list."""

    return []


class RancherHorizontalPodAutoscalerSummary(RancherModel):
    """Typed summary for one HorizontalPodAutoscaler."""

    name: str = Field(
        default="<unknown-hpa>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    target_kind: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "scaleTargetRef", "kind"),
    )
    target_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "scaleTargetRef", "name"),
    )
    min_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "minReplicas"),
    )
    max_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "maxReplicas"),
    )
    current_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "currentReplicas"),
    )
    desired_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "desiredReplicas"),
    )
    metric_count: int = 0
    able_to_scale: bool | None = None
    scaling_active: bool | None = None


class RancherHorizontalPodAutoscalerDetail(RancherHorizontalPodAutoscalerSummary):
    """Typed detail for one HorizontalPodAutoscaler."""

    metric_types: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherHorizontalPodAutoscalerList(RancherModel):
    """Typed list response for HPAs in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    horizontal_pod_autoscaler_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    horizontal_pod_autoscalers: list[RancherHorizontalPodAutoscalerSummary] = Field(
        default_factory=_empty_hpa_summaries,
    )


class RancherResourceQuotaSummary(RancherModel):
    """Typed summary for one ResourceQuota."""

    name: str = Field(
        default="<unknown-resource-quota>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    hard_limit_count: int = 0
    used_count: int = 0
    hard_limit_keys: list[str] = Field(default_factory=list)


class RancherResourceQuotaDetail(RancherResourceQuotaSummary):
    """Typed detail for one ResourceQuota."""

    hard: dict[str, object] = Field(
        default_factory=dict,
        validation_alias=AliasPath("status", "hard"),
    )
    used: dict[str, object] = Field(
        default_factory=dict,
        validation_alias=AliasPath("status", "used"),
    )
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherResourceQuotaList(RancherModel):
    """Typed list response for ResourceQuotas in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    resource_quota_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    resource_quotas: list[RancherResourceQuotaSummary] = Field(
        default_factory=_empty_resource_quota_summaries,
    )


class RancherLimitRangeSummary(RancherModel):
    """Typed summary for one LimitRange."""

    name: str = Field(
        default="<unknown-limit-range>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    limit_count: int = 0
    types_present: list[str] = Field(default_factory=list)


class RancherLimitRangeDetail(RancherLimitRangeSummary):
    """Typed detail for one LimitRange."""

    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherLimitRangeList(RancherModel):
    """Typed list response for LimitRanges in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    limit_range_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    limit_ranges: list[RancherLimitRangeSummary] = Field(
        default_factory=_empty_limit_range_summaries,
    )
