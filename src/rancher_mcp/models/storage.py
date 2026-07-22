"""Typed models for curated Rancher storage reads."""

from pydantic import AliasChoices, AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_storage_class_summaries() -> list["RancherStorageClassSummary"]:
    """Return a typed empty storage-class summary list for Pydantic default factories."""

    return []


def _empty_volume_summaries() -> list["RancherPersistentVolumeSummary"]:
    """Return a typed empty persistent-volume summary list for Pydantic default factories."""

    return []


def _empty_claim_summaries() -> list["RancherPersistentVolumeClaimSummary"]:
    """Return a typed empty persistent-volume-claim summary list for Pydantic default factories."""

    return []


class RancherStorageClassSummary(RancherModel):
    """Typed summary for one storage class."""

    name: str = Field(
        default="<unknown-storage-class>",
        validation_alias=AliasPath("metadata", "name"),
    )
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


class RancherStorageClassList(RancherModel):
    """Typed list response for storage classes."""

    instance: str
    cluster_id: str
    storage_class_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    storage_classes: list[RancherStorageClassSummary] = Field(
        default_factory=_empty_storage_class_summaries
    )


class RancherPersistentVolumeSummary(RancherModel):
    """Typed summary for one persistent volume."""

    name: str = Field(
        default="<unknown-persistent-volume>",
        validation_alias=AliasPath("metadata", "name"),
    )
    phase: str | None = Field(default=None, validation_alias=AliasPath("status", "phase"))
    storage_class_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "storageClassName"),
    )
    capacity_storage: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "capacity", "storage"),
    )
    claim_namespace: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "claimRef", "namespace"),
    )
    claim_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "claimRef", "name"),
    )
    reclaim_policy: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "persistentVolumeReclaimPolicy"),
    )
    access_modes: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("spec", "accessModes"),
    )
    volume_mode: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "volumeMode"),
    )
    volume_source_type: str | None = None


class RancherPersistentVolumeDetail(RancherPersistentVolumeSummary):
    """Typed detail for one persistent volume."""

    finalizers: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("metadata", "finalizers"),
    )
    node_hostnames: list[str] = Field(default_factory=list)
    provisioner: str | None = Field(
        default=None,
        validation_alias=AliasPath(
            "metadata",
            "annotations",
            "pv.kubernetes.io/provisioned-by",
        ),
    )
    payload: dict[str, object] = Field(default_factory=dict)


class RancherPersistentVolumeList(RancherModel):
    """Typed list response for persistent volumes."""

    instance: str
    cluster_id: str
    volume_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    persistent_volumes: list[RancherPersistentVolumeSummary] = Field(
        default_factory=_empty_volume_summaries
    )


class RancherPersistentVolumeClaimSummary(RancherModel):
    """Typed summary for one persistent volume claim."""

    id: str = ""
    name: str = Field(
        default="<unknown-persistent-volume-claim>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    phase: str | None = Field(default=None, validation_alias=AliasPath("status", "phase"))
    storage_class_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "storageClassName"),
    )
    requested_storage: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "resources", "requests", "storage"),
    )
    capacity_storage: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "capacity", "storage"),
    )
    volume_name: str | None = Field(default=None, validation_alias=AliasPath("spec", "volumeName"))
    access_modes: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            AliasPath("status", "accessModes"),
            AliasPath("spec", "accessModes"),
        ),
    )
    volume_mode: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "volumeMode"),
    )


class RancherPersistentVolumeClaimDetail(RancherPersistentVolumeClaimSummary):
    """Typed detail for one persistent volume claim."""

    annotation_keys: list[str] = Field(default_factory=list)
    finalizers: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("metadata", "finalizers"),
    )
    selected_node: str | None = Field(
        default=None,
        validation_alias=AliasPath(
            "metadata",
            "annotations",
            "volume.kubernetes.io/selected-node",
        ),
    )
    payload: dict[str, object] = Field(default_factory=dict)


class RancherPersistentVolumeClaimList(RancherModel):
    """Typed list response for persistent volume claims in one namespace."""

    instance: str
    cluster_id: str
    namespace: str | None
    claim_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    persistent_volume_claims: list[RancherPersistentVolumeClaimSummary] = Field(
        default_factory=_empty_claim_summaries
    )
