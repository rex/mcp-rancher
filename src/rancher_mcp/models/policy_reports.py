"""Typed models for curated PolicyReport reads.

Targets the standardized policy-report API at
``wgpolicyk8s.io/v1alpha2``: PolicyReport (namespaced) and
ClusterPolicyReport (cluster-scoped). Multiple policy engines
emit this format (Kyverno, Kubewarden, Falco).
"""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_policy_report_summaries() -> list["RancherPolicyReportSummary"]:
    """Return a typed empty PolicyReport summary list."""

    return []


def _empty_cluster_policy_report_summaries() -> list["RancherClusterPolicyReportSummary"]:
    """Return a typed empty ClusterPolicyReport summary list."""

    return []


class _PolicyReportBase(RancherModel):
    """Shared PolicyReport summary fields."""

    name: str = Field(
        default="<unknown-policy-report>",
        validation_alias=AliasPath("metadata", "name"),
    )
    pass_count: int = Field(default=0, validation_alias=AliasPath("summary", "pass"))
    fail_count: int = Field(default=0, validation_alias=AliasPath("summary", "fail"))
    warn_count: int = Field(default=0, validation_alias=AliasPath("summary", "warn"))
    error_count: int = Field(default=0, validation_alias=AliasPath("summary", "error"))
    skip_count: int = Field(default=0, validation_alias=AliasPath("summary", "skip"))
    result_count: int = 0
    top_failing_policies: list[str] = Field(default_factory=list)


class RancherPolicyReportSummary(_PolicyReportBase):
    """Typed summary for one namespaced PolicyReport."""

    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )


class RancherPolicyReportDetail(RancherPolicyReportSummary):
    """Typed detail for one PolicyReport."""

    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherPolicyReportList(RancherModel):
    """Typed list response for PolicyReports in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    policy_report_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    policy_reports: list[RancherPolicyReportSummary] = Field(
        default_factory=_empty_policy_report_summaries,
    )


class RancherClusterPolicyReportSummary(_PolicyReportBase):
    """Typed summary for one ClusterPolicyReport."""


class RancherClusterPolicyReportDetail(RancherClusterPolicyReportSummary):
    """Typed detail for one ClusterPolicyReport."""

    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherClusterPolicyReportList(RancherModel):
    """Typed list response for ClusterPolicyReports."""

    instance: str
    cluster_id: str
    cluster_policy_report_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    cluster_policy_reports: list[RancherClusterPolicyReportSummary] = Field(
        default_factory=_empty_cluster_policy_report_summaries,
    )
