"""Deployment workload models."""

from pydantic import AliasPath, Field, computed_field

from rancher_mcp.models.base import RancherClusterScopedDetail, RancherModel
from rancher_mcp.models.workloads.common import (
    RancherCondition,
    RancherWorkloadContainerSummary,
    empty_conditions,
    empty_container_summaries,
)
from rancher_mcp.tools.support.derive import age_days as _compute_age_days


def _empty_deployment_summaries() -> list["RancherDeploymentSummary"]:
    """Return a typed empty deployment-summary list for Pydantic default factories."""

    return []


class RancherDeploymentSummary(RancherModel):
    """Typed summary for one deployment."""

    id: str = ""
    name: str = Field(
        default="<unknown-deployment>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    # The five raw replica ints below are now say-nothing-when-healthy (M-A7 /
    # ADR-0002 rule #3): the `replicas` token collapses ready/desired into one
    # glance-able value, and rule #2/#4's `reason`/`since` promotion covers the
    # not-converged case those ints existed to explain. `exclude=True` only
    # affects serialization — they stay real attributes so existing
    # attribute-asserting tests (and `deployment_ready`/`deployment_rollout_
    # complete`, which consume them directly) are unaffected.
    desired_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "replicas"),
        exclude=True,
    )
    ready_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "readyReplicas"),
        exclude=True,
    )
    available_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "availableReplicas"),
        exclude=True,
    )
    updated_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "updatedReplicas"),
        exclude=True,
    )
    unavailable_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "unavailableReplicas"),
        exclude=True,
    )
    ready: bool | None = None
    rollout_complete: bool | None = None
    # Not-converged diagnosis promoted onto the item (M-A7 / ADR-0002 rules
    # #2/#4): the builder (`tools/workloads/shared.py`) populates these from
    # the deployment's own status conditions only when `ready_replicas !=
    # desired_replicas` or the rollout isn't complete — e.g. `reason:
    # "ProgressDeadlineExceeded"`. All three stay `None` (envelope-dropped)
    # once converged, so a healthy deployment reads as one clean line and an
    # agent never has to `_get` just to learn why a rollout is stuck.
    # `message` (M-B1/B2) rides beside `reason`; `age_days` below derives from
    # `since` so a five-minute-old stall and a five-day-old one read differently.
    reason: str | None = None
    message: str | None = None
    since: str | None = None
    strategy_type: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "strategy", "type"),
    )
    paused: bool | None = Field(default=None, validation_alias=AliasPath("spec", "paused"))
    selector_match_labels: dict[str, str] = Field(
        default_factory=dict,
        validation_alias=AliasPath("spec", "selector", "matchLabels"),
    )
    container_images: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def replicas(self) -> str | None:
        """Collapsed ready/desired token, e.g. ``"2/2"`` (ADR-0002 rule #3 —
        the same treatment ``nodes:"3/3"`` got on ``ClusterHealthSummary``).

        A quick glance already reads exception-shaped (``"1/3"`` signals
        trouble on its own); `reason`/`since` above carry the detail. ``None``
        (envelope-dropped) until the deployment has reported status.
        """

        if self.ready_replicas is None or self.desired_replicas is None:
            return None
        return f"{self.ready_replicas}/{self.desired_replicas}"

    @computed_field
    @property
    def age_days(self) -> int | None:
        """Whole days since `since` (M-B1/B2) — derived at dump time so a
        rollout stuck for five minutes doesn't read the same as one stuck for
        five days. ``None`` (envelope-dropped) whenever `since` is, i.e. once
        converged."""

        return _compute_age_days(self.since)


class RancherDeploymentDetail(RancherDeploymentSummary, RancherClusterScopedDetail):
    """Typed detail for one deployment."""

    revision: str | None = Field(
        default=None,
        validation_alias=AliasPath("metadata", "annotations", "deployment.kubernetes.io/revision"),
    )
    generation: int | None = Field(
        default=None,
        validation_alias=AliasPath("metadata", "generation"),
    )
    observed_generation: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "observedGeneration"),
    )
    service_account_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "template", "spec", "serviceAccountName"),
    )
    min_ready_seconds: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "minReadySeconds"),
    )
    annotation_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(
        default_factory=empty_conditions,
        validation_alias=AliasPath("status", "conditions"),
    )
    containers: list[RancherWorkloadContainerSummary] = Field(
        default_factory=empty_container_summaries,
        validation_alias=AliasPath("spec", "template", "spec", "containers"),
    )
    payload: dict[str, object] = Field(default_factory=dict)


class RancherDeploymentList(RancherModel):
    """Typed list response for deployments in one namespace."""

    instance: str
    cluster_id: str
    namespace: str | None
    deployment_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    deployments: list[RancherDeploymentSummary] = Field(default_factory=_empty_deployment_summaries)
