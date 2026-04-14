"""Typed models for failure-finder convenience tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def _empty_strings() -> list[str]:
    return []


def _empty_failing_pods() -> list["FailingPodSummary"]:
    return []


def _empty_unready_nodes() -> list["UnreadyNodeSummary"]:
    return []


def _empty_stalled_rollouts() -> list["StalledRolloutSummary"]:
    return []


def _empty_svc_no_ep() -> list["ServiceWithoutEndpointsSummary"]:
    return []


def _empty_unbound_pvcs() -> list["UnboundPvcSummary"]:
    return []


def _empty_pdb_blockers() -> list["PdbBlockerSummary"]:
    return []


class FailingPodSummary(RancherModel):
    """One failing pod with context."""

    name: str
    namespace: str
    phase: str | None = None
    reason: str | None = None
    node_name: str | None = None
    owner_kind: str | None = None
    owner_name: str | None = None
    restart_count: int | None = None
    container_states: list[str] = Field(default_factory=_empty_strings)


class FailingPodsList(RancherModel):
    """Result of a failing-pods scan."""

    instance: str
    cluster_id: str
    namespace: str | None = None
    failing_count: int
    pods: list[FailingPodSummary] = Field(
        default_factory=_empty_failing_pods,
    )


class UnreadyNodeSummary(RancherModel):
    """One unready node with context."""

    id: str
    name: str
    state: str | None = None
    roles: list[str] = Field(default_factory=_empty_strings)
    unschedulable: bool | None = None
    ready_condition_status: str | None = None
    ready_condition_message: str | None = None


class UnreadyNodesList(RancherModel):
    """Result of an unready-nodes scan."""

    instance: str
    cluster_id: str | None = None
    unready_count: int
    nodes: list[UnreadyNodeSummary] = Field(
        default_factory=_empty_unready_nodes,
    )


class StalledRolloutSummary(RancherModel):
    """One stalled deployment or statefulset."""

    name: str
    namespace: str
    kind: str
    desired_replicas: int | None = None
    ready_replicas: int | None = None
    updated_replicas: int | None = None
    unavailable_replicas: int | None = None


class StalledRolloutsList(RancherModel):
    """Result of a stalled-rollouts scan."""

    instance: str
    cluster_id: str
    namespace: str
    stalled_count: int
    rollouts: list[StalledRolloutSummary] = Field(
        default_factory=_empty_stalled_rollouts,
    )


class ServiceWithoutEndpointsSummary(RancherModel):
    """One service with no backing endpoints."""

    name: str
    namespace: str
    service_type: str | None = None
    selector: dict[str, str] = Field(default_factory=dict)


class ServicesWithoutEndpointsList(RancherModel):
    """Result of a services-without-endpoints scan."""

    instance: str
    cluster_id: str
    namespace: str
    count: int
    services: list[ServiceWithoutEndpointsSummary] = Field(
        default_factory=_empty_svc_no_ep,
    )


class UnboundPvcSummary(RancherModel):
    """One PVC that is not bound."""

    name: str
    namespace: str
    phase: str | None = None
    storage_class: str | None = None
    requested_storage: str | None = None


class UnboundPvcsList(RancherModel):
    """Result of an unbound-PVCs scan."""

    instance: str
    cluster_id: str
    namespace: str | None = None
    unbound_count: int
    pvcs: list[UnboundPvcSummary] = Field(
        default_factory=_empty_unbound_pvcs,
    )


class PdbBlockerSummary(RancherModel):
    """One PDB currently blocking disruption."""

    name: str
    namespace: str
    min_available: str | None = None
    max_unavailable: str | None = None
    current_healthy: int | None = None
    desired_healthy: int | None = None
    disruptions_allowed: int | None = None
    selector_match_labels: dict[str, str] = Field(default_factory=dict)


class PdbBlockersList(RancherModel):
    """Result of a PDB-blockers scan."""

    instance: str
    cluster_id: str
    namespace: str
    blocking_count: int
    blockers: list[PdbBlockerSummary] = Field(
        default_factory=_empty_pdb_blockers,
    )
