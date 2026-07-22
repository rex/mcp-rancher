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


def _empty_pod_events() -> list["RancherPodEventSummary"]:
    """Return a typed empty pod-event list for Pydantic default factories."""

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
    # `ready_condition` is the pod's raw Kubernetes `Ready` *condition*
    # (renamed from the old `ready` field — used only internally by
    # `classify_pod_health`, below and in `RancherPodList.summary`). Superseded
    # on the wire by the collapsed `ready` token computed further down (M-B4 /
    # ADR-0002 rule #3): `exclude=True` keeps it a real attribute (health
    # classification is unaffected) but drops it from the default dump now
    # that the token already covers the healthy-glance case.
    ready_condition: bool | None = Field(default=None, exclude=True)
    # The now-redundant individual int counts (M-B4 / ADR-0002 rule #3): kept
    # as real attributes (`_pod_summary_from_payload` still populates them,
    # `ready` below still reads them) but `exclude=True`'d from the dump now
    # that `ready:"2/2"` covers the healthy-glance case in one token.
    ready_containers: int | None = Field(default=None, exclude=True)
    total_containers: int | None = Field(default=None, exclude=True)
    restart_count: int | None = None
    pod_ip: str | None = Field(default=None, validation_alias=AliasPath("status", "podIP"))
    node_name: str | None = Field(default=None, validation_alias=AliasPath("spec", "nodeName"))
    qos_class: str | None = Field(default=None, validation_alias=AliasPath("status", "qosClass"))
    owner_kind: str | None = Field(
        default=None,
        validation_alias=AliasPath("metadata", "ownerReferences", 0, "kind"),
        exclude=True,
    )
    owner_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("metadata", "ownerReferences", 0, "name"),
        exclude=True,
    )

    @computed_field
    @property
    def ready(self) -> str | None:
        """Collapsed ready-container token, e.g. ``"2/2"`` (M-B4 / ADR-0002 rule
        #3 — the same treatment ``nodes:"3/3"`` (M-A8) and ``replicas:"2/2"``
        (M-A7) got). ``None`` (envelope-dropped) until container statuses are
        known — a quick glance already reads exception-shaped (``"1/2"``
        signals trouble on its own)."""

        if self.ready_containers is None or self.total_containers is None:
            return None
        return f"{self.ready_containers}/{self.total_containers}"

    @computed_field
    @property
    def owner(self) -> str | None:
        """Collapsed owner-reference token, e.g. ``"ReplicaSet/foo"`` (M-B4).
        ``None`` (envelope-dropped) when the pod has no owner reference."""

        if self.owner_kind is None or self.owner_name is None:
            return None
        return f"{self.owner_kind}/{self.owner_name}"


class RancherPodEventSummary(RancherModel):
    """Typed summary for one Kubernetes event inlined onto a pod detail (M-B4).

    Deliberately leaner than
    :class:`~rancher_mcp.models.ops.events.RancherEventSummary`: the involved
    object (this pod) is already known from the surrounding `pod_get`
    response, so repeating `name`/`namespace`/`involvedKind`/`involvedName`
    per event would be pure plumbing (ADR-0002 rule #1 — "would this field
    ever change what I do next?").
    """

    type: str | None = None
    reason: str | None = None
    message: str | None = None
    count: int | None = None
    last_seen: str | None = None


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
    # Best-effort inline recent events (M-B4) — `pod_get` ONLY, never the
    # list (this field lives on Detail, not Summary). Populated by
    # `pod_events_best_effort` (`tools/pods_services/shared.py`) via a
    # secondary k8s-proxy fetch; empty (envelope-dropped) whenever there are
    # no events OR the secondary fetch fails — events must never break the
    # core pod get.
    events: list[RancherPodEventSummary] = Field(default_factory=_empty_pod_events)
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
    pod_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
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
            counts[classify_pod_health(pod.phase, pod.ready_condition)] += 1
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
    service_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    services: list[RancherServiceSummary] = Field(default_factory=_empty_service_summaries)
