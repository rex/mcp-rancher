"""Typed models for curated Rancher cluster and node reads."""

from typing import cast

from pydantic import AliasChoices, AliasPath, Field, field_validator, model_validator

from rancher_mcp.models.base import RancherModel


def _empty_cluster_summaries() -> list["RancherClusterSummary"]:
    """Return a typed empty cluster-summary list for Pydantic default factories."""

    return []


def _empty_node_summaries() -> list["RancherNodeSummary"]:
    """Return a typed empty node-summary list for Pydantic default factories."""

    return []


def _empty_conditions() -> list["RancherCondition"]:
    """Return a typed empty condition list for Pydantic default factories."""

    return []


def _empty_component_statuses() -> list["RancherClusterComponentStatus"]:
    """Return a typed empty component-status list for Pydantic default factories."""

    return []


class RancherCondition(RancherModel):
    """One Rancher or Kubernetes condition."""

    type: str
    status: str | None = None
    reason: str | None = None
    message: str | None = None


class RancherClusterComponentStatus(RancherModel):
    """One summarized cluster component status."""

    name: str
    healthy: bool | None = None
    message: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _derive_health_from_conditions(cls, value: object) -> object:
        """Derive component health from the embedded Healthy condition when present."""

        if not isinstance(value, dict):
            return value
        payload = dict(cast(dict[str, object], value))
        raw_conditions = payload.get("conditions")
        if not isinstance(raw_conditions, list):
            return payload
        for raw_condition in cast(list[object], raw_conditions):
            if not isinstance(raw_condition, dict):
                continue
            condition = cast(dict[str, object], raw_condition)
            if condition.get("type") != "Healthy":
                continue
            status = condition.get("status")
            if isinstance(status, str):
                lowered = status.lower()
                if lowered == "true":
                    payload["healthy"] = True
                elif lowered == "false":
                    payload["healthy"] = False
            message = condition.get("message")
            if isinstance(message, str):
                payload["message"] = message
            break
        return payload


class RancherClusterSummary(RancherModel):
    """Typed summary for one Rancher cluster."""

    id: str = Field(
        default="<unknown-cluster>",
        validation_alias=AliasChoices("id", "name"),
    )
    name: str = Field(
        default="<unknown-cluster>",
        validation_alias=AliasChoices("name", "id"),
    )
    display_name: str | None = None
    state: str | None = None
    ready: bool | None = None
    provider: str | None = None
    driver: str | None = None
    kubernetes_version: str | None = Field(
        default=None,
        # Read the real Kubernetes version, never the integer `nodeVersion`
        # (a node counter) that the old alias picked up first and coerced to
        # garbage like "8"/"0" (ROADMAP K-3). `version.gitVersion` is the
        # running version for both RKE and imported clusters; the RKE-config
        # paths are spec fallbacks for management clusters that omit status.
        validation_alias=AliasChoices(
            AliasPath("version", "gitVersion"),
            AliasPath("rancherKubernetesEngineConfig", "kubernetesVersion"),
            AliasPath("appliedSpec", "rancherKubernetesEngineConfig", "kubernetesVersion"),
        ),
    )

    @field_validator("kubernetes_version", mode="before")
    @classmethod
    def coerce_kubernetes_version(cls, v: object) -> object:
        return str(v) if v is not None and not isinstance(v, str) else v

    node_count: int | None = None
    cpu_capacity: str | None = Field(default=None, validation_alias=AliasPath("capacity", "cpu"))
    memory_capacity: str | None = Field(
        default=None,
        validation_alias=AliasPath("capacity", "memory"),
    )
    condition_types_true: list[str] = Field(default_factory=list)


class RancherClusterDetail(RancherClusterSummary):
    """Typed detail for one Rancher cluster."""

    api_endpoint: str | None = None
    action_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(
        default_factory=_empty_conditions,
        validation_alias="conditions",
    )
    component_statuses: list[RancherClusterComponentStatus] = Field(
        default_factory=_empty_component_statuses,
        validation_alias="componentStatuses",
    )
    payload: dict[str, object] = Field(default_factory=dict)


class RancherClusterList(RancherModel):
    """Typed list response for Rancher clusters."""

    instance: str
    cluster_count: int
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    clusters: list[RancherClusterSummary] = Field(default_factory=_empty_cluster_summaries)


class RancherNodeSummary(RancherModel):
    """Typed summary for one Rancher-managed node."""

    id: str = Field(
        default="<unknown-node>",
        validation_alias=AliasChoices("id", "name"),
    )
    name: str = Field(
        default="<unknown-node>",
        validation_alias=AliasChoices("name", "id"),
    )
    cluster_id: str | None = None
    hostname: str | None = None
    state: str | None = None
    ready: bool | None = None
    roles: list[str] = Field(default_factory=list)
    kubernetes_version: str | None = Field(
        default=None,
        validation_alias=AliasPath("info", "kubernetes", "kubeletVersion"),
    )
    internal_ip: str | None = Field(default=None, validation_alias="ipAddress")
    external_ip: str | None = Field(default=None, validation_alias="externalIpAddress")
    unschedulable: bool | None = None


class RancherNodeDetail(RancherNodeSummary):
    """Typed detail for one Rancher-managed node."""

    node_name: str | None = Field(default=None, validation_alias="nodeName")
    provider_id: str | None = Field(default=None, validation_alias="providerId")
    pod_cidr: str | None = Field(default=None, validation_alias="podCidr")
    cpu_capacity: str | None = Field(default=None, validation_alias=AliasPath("capacity", "cpu"))
    memory_capacity: str | None = Field(
        default=None,
        validation_alias=AliasPath("capacity", "memory"),
    )
    pod_capacity: str | None = Field(default=None, validation_alias=AliasPath("capacity", "pods"))
    cpu_allocatable: str | None = Field(
        default=None,
        validation_alias=AliasPath("allocatable", "cpu"),
    )
    memory_allocatable: str | None = Field(
        default=None,
        validation_alias=AliasPath("allocatable", "memory"),
    )
    pod_allocatable: str | None = Field(
        default=None,
        validation_alias=AliasPath("allocatable", "pods"),
    )
    action_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(
        default_factory=_empty_conditions,
        validation_alias="conditions",
    )
    payload: dict[str, object] = Field(default_factory=dict)


class RancherNodeList(RancherModel):
    """Typed list response for Rancher nodes."""

    instance: str
    node_count: int
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    nodes: list[RancherNodeSummary] = Field(default_factory=_empty_node_summaries)
