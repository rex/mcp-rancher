"""Typed models for curated Rancher project and namespace reads."""

from pydantic import BaseModel, Field

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


class RancherProjectSummary(BaseModel):
    """Typed summary for one Rancher project."""

    id: str
    name: str
    cluster_id: str | None = None
    state: str | None = None
    description: str | None = None
    monitoring_enabled: bool | None = None
    default_project: bool | None = None
    system_project: bool | None = None
    condition_types_true: list[str] = Field(default_factory=list)


class RancherProjectDetail(RancherProjectSummary):
    """Typed detail for one Rancher project."""

    namespace_id: str | None = None
    pod_security_policy_template_id: str | None = None
    transitioning: str | None = None
    transitioning_message: str | None = None
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(default_factory=_empty_conditions)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherProjectList(BaseModel):
    """Typed list response for Rancher projects."""

    instance: str
    project_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    projects: list[RancherProjectSummary] = Field(default_factory=_empty_project_summaries)


class RancherNamespaceSummary(BaseModel):
    """Typed summary for one downstream namespace."""

    id: str
    name: str
    cluster_id: str
    phase: str | None = None
    state_name: str | None = None
    state_message: str | None = None
    state_error: bool | None = None
    project_id: str | None = None
    project_id_short: str | None = None
    finalizer_count: int | None = None


class RancherNamespaceDetail(RancherNamespaceSummary):
    """Typed detail for one downstream namespace."""

    label_keys: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    finalizers: list[str] = Field(default_factory=list)
    cattle_conditions: list[RancherCondition] = Field(default_factory=_empty_conditions)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherNamespaceList(BaseModel):
    """Typed list response for downstream namespaces."""

    instance: str
    cluster_id: str
    namespace_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    namespaces: list[RancherNamespaceSummary] = Field(default_factory=_empty_namespace_summaries)
