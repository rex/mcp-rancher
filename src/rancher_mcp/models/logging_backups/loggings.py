"""Logging models for curated Rancher logging tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def _empty_cluster_loggings() -> list["RancherClusterLoggingSummary"]:
    """Return a typed empty cluster-logging list for default factories."""

    return []


def _empty_project_loggings() -> list["RancherProjectLoggingSummary"]:
    """Return a typed empty project-logging list for default factories."""

    return []


class RancherClusterLoggingSummary(RancherModel):
    """Typed summary for one Rancher cluster logging resource."""

    id: str = "<unknown-cluster-logging>"
    name: str = "<unknown-cluster-logging>"
    cluster_id: str | None = None
    namespace_id: str | None = None
    state: str | None = None
    transitioning: str | None = None
    transitioning_message: str | None = None
    enable_json_parsing: bool | None = None
    include_system_component: bool | None = None
    output_flush_interval: int | None = None


class RancherClusterLoggingDetail(RancherClusterLoggingSummary):
    """Typed detail for one Rancher cluster logging resource."""

    status: dict[str, object] = Field(default_factory=dict)
    status_keys: list[str] = Field(default_factory=list)
    target_types: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherProjectLoggingSummary(RancherModel):
    """Typed summary for one Rancher project logging resource."""

    id: str = "<unknown-project-logging>"
    name: str = "<unknown-project-logging>"
    project_id: str | None = None
    namespace_id: str | None = None
    state: str | None = None
    transitioning: str | None = None
    transitioning_message: str | None = None
    enable_json_parsing: bool | None = None
    output_flush_interval: int | None = None


class RancherProjectLoggingDetail(RancherProjectLoggingSummary):
    """Typed detail for one Rancher project logging resource."""

    status: dict[str, object] = Field(default_factory=dict)
    status_keys: list[str] = Field(default_factory=list)
    target_types: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherClusterLoggingList(RancherModel):
    """Typed list response for Rancher cluster logging resources."""

    instance: str
    cluster_logging_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    cluster_loggings: list[RancherClusterLoggingSummary] = Field(
        default_factory=_empty_cluster_loggings
    )


class RancherProjectLoggingList(RancherModel):
    """Typed list response for Rancher project logging resources."""

    instance: str
    project_logging_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    project_loggings: list[RancherProjectLoggingSummary] = Field(
        default_factory=_empty_project_loggings
    )
