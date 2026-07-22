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
    """One failing pod with context.

    ``message``/``since``/``age_days`` (M-B1/B2) ride beside ``reason`` so an
    agent never needs a follow-up ``pod_get`` to learn what a waiting/
    terminated container said, or whether the failure is five minutes or five
    days old (ADR-0002 rules #2/#4). Sourced from the same container
    waiting/terminated state as ``reason`` when available, else the pod's own
    ``status.conditions`` (``Ready``/``PodScheduled``/…) — see
    ``tools/ops/find_failing_pods.py``.
    """

    name: str
    namespace: str
    phase: str | None = None
    reason: str | None = None
    message: str | None = None
    since: str | None = None
    age_days: int | None = None
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
    failing_count: int = Field(serialization_alias="count")  # L-2d: uniform count key
    pods: list[FailingPodSummary] = Field(
        default_factory=_empty_failing_pods,
    )


class UnreadyNodeSummary(RancherModel):
    """One unready node with context.

    ``reason``/``since``/``age_days`` (M-B1/B2) come from the node's own
    ``Ready`` condition, alongside the pre-existing ``ready_condition_status``/
    ``ready_condition_message`` — so a node that flipped NotReady five minutes
    ago reads differently from one stuck that way for months.
    """

    id: str
    name: str
    state: str | None = None
    roles: list[str] = Field(default_factory=_empty_strings)
    unschedulable: bool | None = None
    ready_condition_status: str | None = None
    reason: str | None = None
    ready_condition_message: str | None = None
    since: str | None = None
    age_days: int | None = None


class UnreadyNodesList(RancherModel):
    """Result of an unready-nodes scan."""

    instance: str
    cluster_id: str | None = None
    unready_count: int = Field(serialization_alias="count")  # L-2d: uniform count key
    nodes: list[UnreadyNodeSummary] = Field(
        default_factory=_empty_unready_nodes,
    )


class StalledRolloutSummary(RancherModel):
    """One stalled deployment or statefulset.

    ``reason``/``message``/``since``/``age_days`` (M-B1/B2) carry the
    condition-sourced diagnosis (e.g. ``reason: "ProgressDeadlineExceeded"``)
    so an agent doesn't need a follow-up ``deployment_get`` to learn why a
    rollout is stuck, or how long it's been stuck (ADR-0002 rules #2/#4).
    Reuses the same priority-ordered condition pick as ``deployments_list``
    (``tools/workloads/shared.py``'s rollout-diagnosis helper) — one
    definition of "why is this rollout stalled", not two.
    """

    name: str
    namespace: str
    kind: str
    desired_replicas: int | None = None
    ready_replicas: int | None = None
    updated_replicas: int | None = None
    unavailable_replicas: int | None = None
    reason: str | None = None
    message: str | None = None
    since: str | None = None
    age_days: int | None = None


class StalledRolloutsList(RancherModel):
    """Result of a stalled-rollouts scan."""

    instance: str
    cluster_id: str
    namespace: str | None = None
    stalled_count: int = Field(serialization_alias="count")  # L-2d: uniform count key
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
    namespace: str | None = None
    count: int
    services: list[ServiceWithoutEndpointsSummary] = Field(
        default_factory=_empty_svc_no_ep,
    )


class UnboundPvcSummary(RancherModel):
    """One PVC that is not bound.

    ``reason``/``message``/``since``/``age_days`` (M-B1/B2) surface from
    ``status.conditions`` (e.g. a CSI driver's resize/provisioning condition)
    *when the payload exposes them* — plain scheduling-stuck PVCs commonly
    carry no condition at all (that signal lives in Kubernetes Events, out of
    scope here), so these stay ``None``/dropped rather than a guessed value.
    """

    name: str
    namespace: str
    phase: str | None = None
    storage_class: str | None = None
    requested_storage: str | None = None
    reason: str | None = None
    message: str | None = None
    since: str | None = None
    age_days: int | None = None


class UnboundPvcsList(RancherModel):
    """Result of an unbound-PVCs scan."""

    instance: str
    cluster_id: str
    namespace: str | None = None
    unbound_count: int = Field(serialization_alias="count")  # L-2d: uniform count key
    pvcs: list[UnboundPvcSummary] = Field(
        default_factory=_empty_unbound_pvcs,
    )


class PdbBlockerSummary(RancherModel):
    """One PDB currently blocking disruption.

    ``reason``/``message``/``since``/``age_days`` (M-B1/B2) come from the
    PDB's own ``status.conditions`` (typically ``DisruptionAllowed: False``,
    e.g. ``reason: "InsufficientPods"``) when the cluster's Kubernetes
    version populates it — absent on older API servers, in which case these
    stay ``None``/dropped rather than a guessed value.
    """

    name: str
    namespace: str
    min_available: str | None = None
    max_unavailable: str | None = None
    current_healthy: int | None = None
    desired_healthy: int | None = None
    disruptions_allowed: int | None = None
    selector_match_labels: dict[str, str] = Field(default_factory=dict)
    reason: str | None = None
    message: str | None = None
    since: str | None = None
    age_days: int | None = None


class PdbBlockersList(RancherModel):
    """Result of a PDB-blockers scan."""

    instance: str
    cluster_id: str
    namespace: str | None = None
    blocking_count: int = Field(serialization_alias="count")  # L-2d: uniform count key
    blockers: list[PdbBlockerSummary] = Field(
        default_factory=_empty_pdb_blockers,
    )
