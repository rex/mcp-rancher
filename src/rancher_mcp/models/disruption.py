"""Typed models for curated Rancher disruption-management reads."""

from pydantic import AliasPath, Field, field_validator

from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.clusters_nodes import RancherCondition


def _empty_pdb_summaries() -> list["RancherPodDisruptionBudgetSummary"]:
    """Return a typed empty PDB summary list for Pydantic default factories."""

    return []


def _empty_conditions() -> list[RancherCondition]:
    """Return a typed empty condition list for Pydantic default factories."""

    return []


class RancherPodDisruptionBudgetSummary(RancherModel):
    """Typed summary for one pod disruption budget."""

    id: str = ""
    name: str = Field(default="<unknown-pdb>", validation_alias=AliasPath("metadata", "name"))
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    min_available: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "minAvailable"),
    )
    max_unavailable: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "maxUnavailable"),
    )
    current_healthy: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "currentHealthy"),
    )
    desired_healthy: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "desiredHealthy"),
    )
    expected_pods: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "expectedPods"),
    )
    disruptions_allowed: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "disruptionsAllowed"),
    )
    disruption_allowed: bool | None = None
    selector_match_labels: dict[str, str] = Field(
        default_factory=dict,
        validation_alias=AliasPath("spec", "selector", "matchLabels"),
    )

    @field_validator("min_available", "max_unavailable", mode="before")
    @classmethod
    def _coerce_scalar_string_fields(cls, value: object) -> object:
        """Allow Kubernetes scalar availability fields to arrive as ints or strings."""

        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        return value


class RancherPodDisruptionBudgetDetail(RancherPodDisruptionBudgetSummary):
    """Typed detail for one pod disruption budget."""

    annotation_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(
        default_factory=_empty_conditions,
        validation_alias=AliasPath("status", "conditions"),
    )
    payload: dict[str, object] = Field(default_factory=dict)


class RancherPodDisruptionBudgetList(RancherModel):
    """Typed list response for pod disruption budgets in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    budget_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    pod_disruption_budgets: list[RancherPodDisruptionBudgetSummary] = Field(
        default_factory=_empty_pdb_summaries
    )
