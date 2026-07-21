"""Typed models for curated Rancher pod and service reads."""

from typing import cast

from pydantic import (
    AliasChoices,
    AliasPath,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from rancher_mcp.models.base import RancherModel
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


class RancherPodContainerSummary(RancherModel):
    """Typed summary for one pod container."""

    name: str
    image: str | None = None
    ready: bool | None = None
    restart_count: int | None = None
    state: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _derive_state_name(cls, value: object) -> object:
        """Derive the active container state name from the raw Kubernetes payload."""

        if not isinstance(value, dict):
            return value
        payload = dict(cast(dict[str, object], value))
        raw_state = payload.get("state")
        if not isinstance(raw_state, dict):
            return payload
        state = cast(dict[str, object], raw_state)
        for candidate in ("running", "waiting", "terminated"):
            if isinstance(state.get(candidate), dict):
                payload["state"] = candidate
                break
        return payload


class RancherPodSummary(RancherModel):
    """Typed summary for one pod."""

    id: str = Field(
        default="<unknown-pod>",
        validation_alias=AliasChoices("id", AliasPath("metadata", "name")),
    )
    name: str = Field(
        default="<unknown-pod>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    phase: str | None = Field(default=None, validation_alias=AliasPath("status", "phase"))
    ready: bool | None = None
    ready_containers: int | None = None
    total_containers: int | None = None
    restart_count: int | None = None
    pod_ip: str | None = Field(default=None, validation_alias=AliasPath("status", "podIP"))
    node_name: str | None = Field(default=None, validation_alias=AliasPath("spec", "nodeName"))
    qos_class: str | None = Field(default=None, validation_alias=AliasPath("status", "qosClass"))
    owner_kind: str | None = Field(
        default=None,
        validation_alias=AliasPath("metadata", "ownerReferences", 0, "kind"),
    )
    owner_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("metadata", "ownerReferences", 0, "name"),
    )


class RancherPodDetail(RancherPodSummary):
    """Typed detail for one pod."""

    host_ip: str | None = Field(default=None, validation_alias=AliasPath("status", "hostIP"))
    service_account_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "serviceAccountName"),
    )
    link_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(
        default_factory=_empty_conditions,
        validation_alias=AliasPath("status", "conditions"),
    )
    containers: list[RancherPodContainerSummary] = Field(
        default_factory=_empty_container_summaries,
        validation_alias=AliasPath("status", "containerStatuses"),
    )
    payload: dict[str, object] = Field(default_factory=dict)


def classify_pod_health(phase: str | None, ready: bool | None) -> str:
    """Classify a pod's phase + readiness into a shared health bucket.

    Returns one of ``running`` / ``succeeded`` / ``pending`` / ``failed`` /
    ``unhealthy`` — the single canonical definition shared by
    :attr:`RancherPodList.summary` (L-2c) and the namespace/project rollups
    (``models/ops/rollups.py`` + ``tools/ops/rollups.py``, M-A4) so every
    curated pod-health surface agrees on what each bucket means.
    ``succeeded`` (terminal Job pods) is deliberately excluded from every
    other bucket so a completed Job never makes a healthy namespace/project
    read half-down. ``unhealthy`` covers running-but-not-ready pods and any
    unrecognized or missing phase (e.g. ``Unknown``).
    """

    normalized = (phase or "").lower()
    if normalized == "succeeded":
        return "succeeded"
    if normalized == "pending":
        return "pending"
    if normalized == "failed":
        return "failed"
    if normalized == "running" and ready is not False:
        return "running"
    return "unhealthy"


class RancherPodList(RancherModel):
    """Typed list response for pods in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    pod_count: int
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    pods: list[RancherPodSummary] = Field(default_factory=_empty_pod_summaries)

    @computed_field
    @property
    def summary(self) -> dict[str, int]:
        """Phase counts so a namespace whose Completed migration Jobs sit beside
        live pods doesn't read as half-down (L-2c). ``unhealthy`` is the field an
        agent branches on: running-but-not-ready or an unknown/crash phase.
        ``succeeded`` (terminal Jobs) is separated from ``running`` health."""

        counts = {"running": 0, "succeeded": 0, "pending": 0, "failed": 0, "unhealthy": 0}
        for pod in self.pods:
            counts[classify_pod_health(pod.phase, pod.ready)] += 1
        return counts


class RancherServicePortSummary(RancherModel):
    """Typed summary for one service port."""

    name: str | None = None
    protocol: str | None = None
    port: int | None = None
    target_port: str | None = None

    @field_validator("target_port", mode="before")
    @classmethod
    def _coerce_target_port(cls, value: object) -> object:
        """Accept integer or string targetPort values from Kubernetes service specs."""

        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        return value


class RancherServiceSummary(RancherModel):
    """Typed summary for one service."""

    id: str = Field(
        default="<unknown-service>",
        validation_alias=AliasChoices("id", AliasPath("metadata", "name")),
    )
    name: str = Field(
        default="<unknown-service>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    service_type: str | None = Field(default=None, validation_alias=AliasPath("spec", "type"))
    cluster_ip: str | None = Field(default=None, validation_alias=AliasPath("spec", "clusterIP"))
    state_name: str | None = Field(
        default=None, validation_alias=AliasPath("metadata", "state", "name")
    )
    state_message: str | None = Field(
        default=None,
        validation_alias=AliasPath("metadata", "state", "message"),
    )
    selector: dict[str, str] = Field(
        default_factory=dict,
        validation_alias=AliasPath("spec", "selector"),
    )
    ports: list[RancherServicePortSummary] = Field(
        default_factory=_empty_service_ports,
        validation_alias=AliasPath("spec", "ports"),
    )


class RancherServiceDetail(RancherServiceSummary):
    """Typed detail for one service."""

    session_affinity: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "sessionAffinity"),
    )
    internal_traffic_policy: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "internalTrafficPolicy"),
    )
    external_ips: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("spec", "externalIPs"),
    )
    relationship_types: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherServiceList(RancherModel):
    """Typed list response for services in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    service_count: int
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    services: list[RancherServiceSummary] = Field(default_factory=_empty_service_summaries)
