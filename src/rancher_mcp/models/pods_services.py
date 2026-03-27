"""Typed models for curated Rancher pod and service reads."""

from pydantic import BaseModel, Field

from rancher_mcp.models.clusters_nodes import RancherCondition


def _empty_pod_summaries() -> list["RancherPodSummary"]:
    """Return a typed empty pod-summary list for Pydantic default factories."""

    return []


def _empty_service_summaries() -> list["RancherServiceSummary"]:
    """Return a typed empty service-summary list for Pydantic default factories."""

    return []


def _empty_conditions() -> list[RancherCondition]:
    """Return a typed empty condition list for Pydantic default factories."""

    return []


def _empty_container_summaries() -> list["RancherPodContainerSummary"]:
    """Return a typed empty container-summary list for Pydantic default factories."""

    return []


def _empty_service_ports() -> list["RancherServicePortSummary"]:
    """Return a typed empty service-port list for Pydantic default factories."""

    return []


class RancherPodContainerSummary(BaseModel):
    """Typed summary for one pod container."""

    name: str
    image: str | None = None
    ready: bool | None = None
    restart_count: int | None = None
    state: str | None = None


class RancherPodSummary(BaseModel):
    """Typed summary for one pod."""

    id: str
    name: str
    namespace: str
    phase: str | None = None
    ready: bool | None = None
    ready_containers: int | None = None
    total_containers: int | None = None
    restart_count: int | None = None
    pod_ip: str | None = None
    node_name: str | None = None
    qos_class: str | None = None
    owner_kind: str | None = None
    owner_name: str | None = None


class RancherPodDetail(RancherPodSummary):
    """Typed detail for one pod."""

    host_ip: str | None = None
    service_account_name: str | None = None
    link_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(default_factory=_empty_conditions)
    containers: list[RancherPodContainerSummary] = Field(default_factory=_empty_container_summaries)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherPodList(BaseModel):
    """Typed list response for pods in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    pod_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    pods: list[RancherPodSummary] = Field(default_factory=_empty_pod_summaries)


class RancherServicePortSummary(BaseModel):
    """Typed summary for one service port."""

    name: str | None = None
    protocol: str | None = None
    port: int | None = None
    target_port: str | None = None


class RancherServiceSummary(BaseModel):
    """Typed summary for one service."""

    id: str
    name: str
    namespace: str
    service_type: str | None = None
    cluster_ip: str | None = None
    state_name: str | None = None
    state_message: str | None = None
    selector: dict[str, str] = Field(default_factory=dict)
    ports: list[RancherServicePortSummary] = Field(default_factory=_empty_service_ports)


class RancherServiceDetail(RancherServiceSummary):
    """Typed detail for one service."""

    session_affinity: str | None = None
    internal_traffic_policy: str | None = None
    external_ips: list[str] = Field(default_factory=list)
    relationship_types: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherServiceList(BaseModel):
    """Typed list response for services in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    service_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    services: list[RancherServiceSummary] = Field(default_factory=_empty_service_summaries)
