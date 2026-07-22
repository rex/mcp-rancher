"""ReplicaSet workload models."""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherClusterScopedDetail, RancherModel


def _empty_replicaset_summaries() -> list["RancherReplicaSetSummary"]:
    """Return a typed empty replicaset-summary list for Pydantic default factories."""

    return []


class RancherReplicaSetSummary(RancherModel):
    """Typed summary for one replicaset."""

    id: str = ""
    name: str = Field(
        default="<unknown-replicaset>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "replicas"),
    )
    ready_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "readyReplicas"),
    )
    available_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "availableReplicas"),
    )
    fully_labeled_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "fullyLabeledReplicas"),
    )
    observed_generation: int | None = Field(
        default=None,
        validation_alias=AliasPath("status", "observedGeneration"),
    )
    ready: bool | None = None
    selector_match_labels: dict[str, str] = Field(
        default_factory=dict,
        validation_alias=AliasPath("spec", "selector", "matchLabels"),
    )
    container_images: list[str] = Field(default_factory=list)


class RancherReplicaSetDetail(RancherReplicaSetSummary, RancherClusterScopedDetail):
    """Typed detail for one replicaset."""

    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherReplicaSetList(RancherModel):
    """Typed list response for replicasets in one namespace."""

    instance: str
    cluster_id: str
    namespace: str | None
    replica_set_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    replica_sets: list[RancherReplicaSetSummary] = Field(
        default_factory=_empty_replicaset_summaries
    )
