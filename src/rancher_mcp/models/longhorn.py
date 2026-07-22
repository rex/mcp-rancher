"""Typed models for curated Longhorn reads.

Targets the Longhorn storage CRDs at ``longhorn.io/v1beta2``: Volume,
Node, Backup, and Snapshot. All four are namespaced — Longhorn
installs to ``longhorn-system`` by default, but the chart allows
overrides, so the namespace is always a required tool argument.

Distinct from the existing ``storage`` pack, which covers the
Kubernetes-native storage primitives (StorageClass, PV, PVC).
"""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_volume_summaries() -> list["RancherLonghornVolumeSummary"]:
    """Return a typed empty Longhorn-volume summary list."""

    return []


def _empty_node_summaries() -> list["RancherLonghornNodeSummary"]:
    """Return a typed empty Longhorn-node summary list."""

    return []


def _empty_backup_summaries() -> list["RancherLonghornBackupSummary"]:
    """Return a typed empty Longhorn-backup summary list."""

    return []


def _empty_snapshot_summaries() -> list["RancherLonghornSnapshotSummary"]:
    """Return a typed empty Longhorn-snapshot summary list."""

    return []


class _LonghornNamedBase(RancherModel):
    """Shared name/namespace fields for namespaced Longhorn resources."""

    name: str = Field(
        default="<unknown>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )


class RancherLonghornVolumeSummary(_LonghornNamedBase):
    """Typed summary for one Longhorn Volume."""

    state: str | None = Field(default=None, validation_alias=AliasPath("status", "state"))
    robustness: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "robustness"),
    )
    size: str | None = Field(default=None, validation_alias=AliasPath("spec", "size"))
    number_of_replicas: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "numberOfReplicas"),
    )
    access_mode: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "accessMode"),
    )
    frontend: str | None = Field(default=None, validation_alias=AliasPath("spec", "frontend"))
    current_node_id: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "currentNodeID"),
    )


class RancherLonghornVolumeDetail(RancherLonghornVolumeSummary):
    """Typed detail for one Longhorn Volume."""

    current_image: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "currentImage"),
    )
    actual_size: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "actualSize"),
    )
    restore_required: bool | None = Field(
        default=None,
        validation_alias=AliasPath("status", "restoreRequired"),
    )
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherLonghornVolumeList(RancherModel):
    """Typed list response for Longhorn volumes in one namespace."""

    instance: str
    cluster_id: str
    namespace: str | None
    volume_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    volumes: list[RancherLonghornVolumeSummary] = Field(
        default_factory=_empty_volume_summaries,
    )


class RancherLonghornNodeSummary(_LonghornNamedBase):
    """Typed summary for one Longhorn Node."""

    allow_scheduling: bool | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "allowScheduling"),
    )
    eviction_requested: bool | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "evictionRequested"),
    )
    tags: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("spec", "tags"),
    )
    ready: bool | None = None
    schedulable: bool | None = None
    disk_count: int | None = None


class RancherLonghornNodeDetail(RancherLonghornNodeSummary):
    """Typed detail for one Longhorn Node."""

    storage_available_total: int | None = None
    storage_maximum_total: int | None = None
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherLonghornNodeList(RancherModel):
    """Typed list response for Longhorn nodes in one namespace."""

    instance: str
    cluster_id: str
    namespace: str | None
    node_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    nodes: list[RancherLonghornNodeSummary] = Field(
        default_factory=_empty_node_summaries,
    )


class RancherLonghornBackupSummary(_LonghornNamedBase):
    """Typed summary for one Longhorn Backup."""

    state: str | None = Field(default=None, validation_alias=AliasPath("status", "state"))
    volume_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "volumeName"),
    )
    snapshot_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "snapshotName"),
    )
    size: str | None = Field(default=None, validation_alias=AliasPath("status", "size"))
    error_message: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "error"),
    )


class RancherLonghornBackupDetail(RancherLonghornBackupSummary):
    """Typed detail for one Longhorn Backup."""

    backup_created_at: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "backupCreatedAt"),
    )
    last_synced_at: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "lastSyncedAt"),
    )
    url: str | None = Field(default=None, validation_alias=AliasPath("status", "url"))
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherLonghornBackupList(RancherModel):
    """Typed list response for Longhorn backups in one namespace."""

    instance: str
    cluster_id: str
    namespace: str | None
    backup_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    backups: list[RancherLonghornBackupSummary] = Field(
        default_factory=_empty_backup_summaries,
    )


class RancherLonghornSnapshotSummary(_LonghornNamedBase):
    """Typed summary for one Longhorn Snapshot."""

    volume: str | None = Field(default=None, validation_alias=AliasPath("spec", "volume"))
    creation_time: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "creationTime"),
    )
    size: str | None = Field(default=None, validation_alias=AliasPath("status", "size"))
    ready_to_use: bool | None = Field(
        default=None,
        validation_alias=AliasPath("status", "readyToUse"),
    )


class RancherLonghornSnapshotDetail(RancherLonghornSnapshotSummary):
    """Typed detail for one Longhorn Snapshot."""

    parent: str | None = Field(default=None, validation_alias=AliasPath("status", "parent"))
    children: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("status", "children"),
    )
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherLonghornSnapshotList(RancherModel):
    """Typed list response for Longhorn snapshots in one namespace."""

    instance: str
    cluster_id: str
    namespace: str | None
    snapshot_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    snapshots: list[RancherLonghornSnapshotSummary] = Field(
        default_factory=_empty_snapshot_summaries,
    )
