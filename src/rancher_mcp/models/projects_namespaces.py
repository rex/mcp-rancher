"""Typed models for curated Rancher project and namespace reads."""

from pydantic import AliasChoices, AliasPath, Field

from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.clusters_nodes import RancherCondition


def _empty_project_summaries() -> list["RancherProjectSummary"]:
    """Return a typed empty project-summary list for Pydantic default factories."""

    return []


def _empty_namespace_summaries() -> list["RancherNamespaceSummary"]:
    """Return a typed empty namespace-summary list for Pydantic default factories."""

    return []


def _empty_conditions() -> list[RancherCondition]:
    """Return a typed empty condition list for Pydantic default factories."""

    return []


class RancherProjectSummary(RancherModel):
    """Typed summary for one Rancher project."""

    id: str
    name: str
    cluster_id: str | None = None
    state: str | None = None
    description: str | None = None
    monitoring_enabled: bool | None = Field(
        default=None, validation_alias="enableProjectMonitoring"
    )
    default_project: bool | None = None
    system_project: bool | None = None
    condition_types_true: list[str] = Field(default_factory=list)


class RancherProjectDetail(RancherProjectSummary):
    """Typed detail for one Rancher project."""

    namespace_id: str | None = Field(default=None, validation_alias="namespaceId")
    pod_security_policy_template_id: str | None = Field(
        default=None,
        validation_alias="podSecurityPolicyTemplateId",
    )
    transitioning: str | None = None
    transitioning_message: str | None = Field(default=None, validation_alias="transitioningMessage")
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(
        default_factory=_empty_conditions,
        validation_alias="conditions",
    )
    payload: dict[str, object] = Field(default_factory=dict)


class RancherProjectList(RancherModel):
    """Typed list response for Rancher projects."""

    instance: str
    project_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    projects: list[RancherProjectSummary] = Field(default_factory=_empty_project_summaries)


class RancherNamespaceSummary(RancherModel):
    """Typed summary for one downstream namespace."""

    id: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasChoices("id", AliasPath("metadata", "name")),
    )
    name: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "name"),
    )
    cluster_id: str = ""
    phase: str | None = Field(default=None, validation_alias=AliasPath("status", "phase"))
    state_name: str | None = Field(
        default=None, validation_alias=AliasPath("metadata", "state", "name")
    )
    state_message: str | None = Field(
        default=None,
        validation_alias=AliasPath("metadata", "state", "message"),
    )
    state_error: bool | None = Field(
        default=None,
        validation_alias=AliasPath("metadata", "state", "error"),
    )
    project_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            AliasPath("metadata", "annotations", "field.cattle.io/projectId"),
            AliasPath("metadata", "labels", "field.cattle.io/projectId"),
        ),
    )
    project_id_short: str | None = Field(
        default=None,
        validation_alias=AliasPath("metadata", "labels", "field.cattle.io/projectId"),
    )
    finalizer_count: int | None = None


class RancherNamespaceDetail(RancherNamespaceSummary):
    """Typed detail for one downstream namespace."""

    label_keys: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    finalizers: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("metadata", "finalizers"),
    )
    cattle_conditions: list[RancherCondition] = Field(default_factory=_empty_conditions)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherNamespaceList(RancherModel):
    """Typed list response for downstream namespaces."""

    instance: str
    cluster_id: str
    namespace_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    namespaces: list[RancherNamespaceSummary] = Field(default_factory=_empty_namespace_summaries)
