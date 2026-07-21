"""Typed models for curated Rancher cluster and node reads."""

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
from rancher_mcp.units import humanize_memory, percent


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


def _empty_cluster_issues() -> list["ClusterIssue"]:
    """Return a typed empty cluster-issue list for Pydantic default factories."""

    return []


class RancherCondition(RancherModel):
    """One Rancher or Kubernetes condition."""

    type: str
    status: str | None = None
    reason: str | None = None
    message: str | None = None
    last_transition_time: str | None = Field(default=None, validation_alias="lastTransitionTime")


class ClusterIssue(RancherModel):
    """One structured cluster-health issue — exception-shaped signal.

    Carries the diagnosis inline (``severity`` + ``since``/``age_days`` +
    ``reason``/``message``) so an agent branches without a second call
    (ADR-0002 rules #2/#4). ``since``/``age_days`` separate a five-year-old
    benign state from a live incident — the single highest-value addition in
    the field spec.

    Defined here (alongside ``RancherCondition``, not in
    ``models/ops/cluster_health.py``) so both ``cluster_health_check`` (L-2b)
    and ``cluster_get`` (M-A3) can share one type without a models-layer
    circular import — ``models/ops/cluster_health.py`` already imports
    ``RancherCondition`` from this module. It re-exports ``ClusterIssue`` from
    its original location for backward compatibility.
    """

    type: str
    status: str | None = None
    severity: str = "warning"
    since: str | None = None
    age_days: int | None = None
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
    # condition_types_true REMOVED (M-A3 / ADR-0002): the echo of every
    # True-status condition type was noise once conditions are exception-
    # shaped. RancherClusterDetail's `issues[]` + `condition_counts` below are
    # its typed replacement — see also L-2b's `cluster_health_check`.


class RancherClusterDetail(RancherClusterSummary):
    """Typed detail for one Rancher cluster."""

    api_endpoint: str | None = None
    action_keys: list[str] = Field(default_factory=list)
    # Raw echoes stay OFF the default dump (M-A3 / ADR-0002 rule #2): `issues[]`
    # + `condition_counts` below are the typed replacement signal. The
    # attributes stay populated from the payload — `exclude=True` only affects
    # serialization, so attribute-asserting callers/tests are unaffected.
    conditions: list[RancherCondition] = Field(
        default_factory=_empty_conditions,
        validation_alias="conditions",
        exclude=True,
    )
    component_statuses: list[RancherClusterComponentStatus] = Field(
        default_factory=_empty_component_statuses,
        validation_alias="componentStatuses",
        exclude=True,
    )
    issues: list[ClusterIssue] = Field(default_factory=_empty_cluster_issues)
    condition_counts: dict[str, int] = Field(default_factory=dict)
    payload: dict[str, object] = Field(default_factory=dict)

    @computed_field
    @property
    def memory_capacity_human(self) -> str | None:
        """Cluster memory in human binary units (never raw ``Ki``) — mirrors
        node_get's L-2a derivation (ADR-0002 rule #3)."""

        return humanize_memory(self.memory_capacity)


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
    # Operational diagnostics K-2 dropped with the raw payload — restored as
    # always-on typed fields (L-2a / ADR-0002): headroom and host identity.
    requested_cpu: str | None = Field(default=None, validation_alias=AliasPath("requested", "cpu"))
    requested_memory: str | None = Field(
        default=None,
        validation_alias=AliasPath("requested", "memory"),
    )
    os_image: str | None = Field(
        default=None,
        validation_alias=AliasPath("info", "os", "operatingSystem"),
    )
    kernel_version: str | None = Field(
        default=None,
        validation_alias=AliasPath("info", "os", "kernelVersion"),
    )
    container_runtime: str | None = Field(
        default=None,
        validation_alias=AliasPath("info", "os", "dockerVersion"),
    )
    action_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(
        default_factory=_empty_conditions,
        validation_alias="conditions",
    )
    payload: dict[str, object] = Field(default_factory=dict)

    @field_validator("conditions")
    @classmethod
    def _dedupe_conditions(cls, value: list[RancherCondition]) -> list[RancherCondition]:
        """Drop duplicate condition types — Rancher sometimes emits Ready twice."""

        seen: set[str] = set()
        unique: list[RancherCondition] = []
        for condition in value:
            if condition.type in seen:
                continue
            seen.add(condition.type)
            unique.append(condition)
        return unique

    @computed_field
    @property
    def memory_capacity_human(self) -> str | None:
        """Node memory in human binary units (never raw ``Ki``) — ADR-0002 rule #3."""

        return humanize_memory(self.memory_capacity)

    @computed_field
    @property
    def cpu_utilization(self) -> str | None:
        """Requested-vs-capacity CPU as a percent — the headroom read, derived."""

        return percent(self.requested_cpu, self.cpu_capacity)

    @computed_field
    @property
    def memory_utilization(self) -> str | None:
        """Requested-vs-capacity memory as a percent, derived."""

        return percent(self.requested_memory, self.memory_capacity)


class RancherNodeList(RancherModel):
    """Typed list response for Rancher nodes."""

    instance: str
    node_count: int
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    nodes: list[RancherNodeSummary] = Field(default_factory=_empty_node_summaries)

    @computed_field
    @property
    def summary(self) -> dict[str, object]:
        """Fleet roll-up — ready/notReady/unschedulable counts and a version
        histogram (the upgrade matrix). Derived so the agent needn't tally
        nodes by hand across a cluster mid-roll (L-2a / ADR-0002 rule #3)."""

        versions: dict[str, int] = {}
        ready = not_ready = unschedulable = 0
        for node in self.nodes:
            if node.kubernetes_version:
                versions[node.kubernetes_version] = versions.get(node.kubernetes_version, 0) + 1
            if node.ready is True:
                ready += 1
            elif node.ready is False:
                not_ready += 1
            if node.unschedulable is True:
                unschedulable += 1
        return {
            "ready": ready,
            "notReady": not_ready,
            "unschedulable": unschedulable,
            "versions": versions,
        }
