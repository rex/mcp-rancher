"""Typed models for curated Rancher logging-pipeline reads.

Targets the Banzai Logging Operator CRDs at
``logging.banzaicloud.io/v1beta1``: Output / ClusterOutput
(destination configs) and Flow / ClusterFlow (routing rules).

Distinct from Rancher's legacy ``cluster_loggings`` and
``project_loggings`` types (Norman, in the ``logging_backups`` pack).
"""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_output_summaries() -> list["RancherLoggingOutputSummary"]:
    """Return a typed empty Output summary list."""

    return []


def _empty_cluster_output_summaries() -> list["RancherLoggingClusterOutputSummary"]:
    """Return a typed empty ClusterOutput summary list."""

    return []


def _empty_flow_summaries() -> list["RancherLoggingFlowSummary"]:
    """Return a typed empty Flow summary list."""

    return []


def _empty_cluster_flow_summaries() -> list["RancherLoggingClusterFlowSummary"]:
    """Return a typed empty ClusterFlow summary list."""

    return []


class RancherLoggingOutputSummary(RancherModel):
    """Typed summary for one Banzai logging Output."""

    name: str = Field(
        default="<unknown-output>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    output_type: str | None = None
    logging_ref: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "loggingRef"),
    )


class RancherLoggingOutputDetail(RancherLoggingOutputSummary):
    """Typed detail for one Banzai logging Output."""

    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherLoggingOutputList(RancherModel):
    """Typed list response for Banzai logging Outputs."""

    instance: str
    cluster_id: str
    namespace: str | None
    output_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    outputs: list[RancherLoggingOutputSummary] = Field(
        default_factory=_empty_output_summaries,
    )


class RancherLoggingClusterOutputSummary(RancherModel):
    """Typed summary for one Banzai logging ClusterOutput."""

    name: str = Field(
        default="<unknown-cluster-output>",
        validation_alias=AliasPath("metadata", "name"),
    )
    output_type: str | None = None
    logging_ref: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "loggingRef"),
    )


class RancherLoggingClusterOutputDetail(RancherLoggingClusterOutputSummary):
    """Typed detail for one Banzai logging ClusterOutput."""

    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherLoggingClusterOutputList(RancherModel):
    """Typed list response for Banzai logging ClusterOutputs."""

    instance: str
    cluster_id: str
    cluster_output_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    cluster_outputs: list[RancherLoggingClusterOutputSummary] = Field(
        default_factory=_empty_cluster_output_summaries,
    )


class RancherLoggingFlowSummary(RancherModel):
    """Typed summary for one Banzai logging Flow."""

    name: str = Field(
        default="<unknown-flow>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    logging_ref: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "loggingRef"),
    )
    local_output_refs: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("spec", "localOutputRefs"),
    )
    global_output_refs: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("spec", "globalOutputRefs"),
    )
    match_count: int = 0
    filter_count: int = 0


class RancherLoggingFlowDetail(RancherLoggingFlowSummary):
    """Typed detail for one Banzai logging Flow."""

    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherLoggingFlowList(RancherModel):
    """Typed list response for Banzai logging Flows."""

    instance: str
    cluster_id: str
    namespace: str | None
    flow_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    flows: list[RancherLoggingFlowSummary] = Field(default_factory=_empty_flow_summaries)


class RancherLoggingClusterFlowSummary(RancherModel):
    """Typed summary for one Banzai logging ClusterFlow."""

    name: str = Field(
        default="<unknown-cluster-flow>",
        validation_alias=AliasPath("metadata", "name"),
    )
    logging_ref: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "loggingRef"),
    )
    local_output_refs: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("spec", "localOutputRefs"),
    )
    global_output_refs: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("spec", "globalOutputRefs"),
    )
    match_count: int = 0
    filter_count: int = 0


class RancherLoggingClusterFlowDetail(RancherLoggingClusterFlowSummary):
    """Typed detail for one Banzai logging ClusterFlow."""

    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherLoggingClusterFlowList(RancherModel):
    """Typed list response for Banzai logging ClusterFlows."""

    instance: str
    cluster_id: str
    cluster_flow_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    cluster_flows: list[RancherLoggingClusterFlowSummary] = Field(
        default_factory=_empty_cluster_flow_summaries,
    )
