"""Typed models for curated Rancher storage reads."""

from pydantic import BaseModel, Field


def _empty_storage_class_summaries() -> list["RancherStorageClassSummary"]:
    """Return a typed empty storage-class summary list for Pydantic default factories."""

    return []


def _empty_volume_summaries() -> list["RancherPersistentVolumeSummary"]:
    """Return a typed empty persistent-volume summary list for Pydantic default factories."""

    return []


def _empty_claim_summaries() -> list["RancherPersistentVolumeClaimSummary"]:
    """Return a typed empty persistent-volume-claim summary list for Pydantic default factories."""

    return []


class RancherStorageClassSummary(BaseModel):
    """Typed summary for one storage class."""

    name: str
    provisioner: str | None = None
    reclaim_policy: str | None = None
    volume_binding_mode: str | None = None
    allow_volume_expansion: bool | None = None
    default_class: bool | None = None
    parameter_keys: list[str] = Field(default_factory=list)


class RancherStorageClassDetail(RancherStorageClassSummary):
    """Typed detail for one storage class."""

    mount_options: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherStorageClassList(BaseModel):
    """Typed list response for storage classes."""

    instance: str
    cluster_id: str
    storage_class_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    storage_classes: list[RancherStorageClassSummary] = Field(
        default_factory=_empty_storage_class_summaries
    )


class RancherPersistentVolumeSummary(BaseModel):
    """Typed summary for one persistent volume."""

    name: str
    phase: str | None = None
    storage_class_name: str | None = None
    capacity_storage: str | None = None
    claim_namespace: str | None = None
    claim_name: str | None = None
    reclaim_policy: str | None = None
    access_modes: list[str] = Field(default_factory=list)
    volume_mode: str | None = None
    volume_source_type: str | None = None


class RancherPersistentVolumeDetail(RancherPersistentVolumeSummary):
    """Typed detail for one persistent volume."""

    finalizers: list[str] = Field(default_factory=list)
    node_hostnames: list[str] = Field(default_factory=list)
    provisioner: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)


class RancherPersistentVolumeList(BaseModel):
    """Typed list response for persistent volumes."""

    instance: str
    cluster_id: str
    volume_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    persistent_volumes: list[RancherPersistentVolumeSummary] = Field(
        default_factory=_empty_volume_summaries
    )


class RancherPersistentVolumeClaimSummary(BaseModel):
    """Typed summary for one persistent volume claim."""

    id: str
    name: str
    namespace: str
    phase: str | None = None
    storage_class_name: str | None = None
    requested_storage: str | None = None
    capacity_storage: str | None = None
    volume_name: str | None = None
    access_modes: list[str] = Field(default_factory=list)
    volume_mode: str | None = None


class RancherPersistentVolumeClaimDetail(RancherPersistentVolumeClaimSummary):
    """Typed detail for one persistent volume claim."""

    annotation_keys: list[str] = Field(default_factory=list)
    finalizers: list[str] = Field(default_factory=list)
    selected_node: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)


class RancherPersistentVolumeClaimList(BaseModel):
    """Typed list response for persistent volume claims in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    claim_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    persistent_volume_claims: list[RancherPersistentVolumeClaimSummary] = Field(
        default_factory=_empty_claim_summaries
    )
