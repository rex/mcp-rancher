"""Typed models for curated Rancher disruption-management reads."""

from pydantic import BaseModel, Field

from rancher_mcp.models.clusters_nodes import RancherCondition


def _empty_pdb_summaries() -> list["RancherPodDisruptionBudgetSummary"]:
    """Return a typed empty PDB summary list for Pydantic default factories."""

    return []


def _empty_conditions() -> list[RancherCondition]:
    """Return a typed empty condition list for Pydantic default factories."""

    return []


class RancherPodDisruptionBudgetSummary(BaseModel):
    """Typed summary for one pod disruption budget."""

    id: str
    name: str
    namespace: str
    min_available: str | None = None
    max_unavailable: str | None = None
    current_healthy: int | None = None
    desired_healthy: int | None = None
    expected_pods: int | None = None
    disruptions_allowed: int | None = None
    disruption_allowed: bool | None = None
    selector_match_labels: dict[str, str] = Field(default_factory=dict)


class RancherPodDisruptionBudgetDetail(RancherPodDisruptionBudgetSummary):
    """Typed detail for one pod disruption budget."""

    annotation_keys: list[str] = Field(default_factory=list)
    conditions: list[RancherCondition] = Field(default_factory=_empty_conditions)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherPodDisruptionBudgetList(BaseModel):
    """Typed list response for pod disruption budgets in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    budget_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    pod_disruption_budgets: list[RancherPodDisruptionBudgetSummary] = Field(
        default_factory=_empty_pdb_summaries
    )
