"""Typed models for curated Rancher Backup Operator reads.

The Rancher Backup Operator runs on the Rancher *local* cluster and
defines two cluster-scoped CRDs in ``resources.cattle.io/v1``:
``Backup`` and ``Restore``. These are independent of RKE etcd backups
(those are Norman ``etcdbackup`` resources, covered by the existing
``logging_backups`` pack).
"""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_backup_summaries() -> list["RancherBackupSummary"]:
    """Return a typed empty backup-summary list for Pydantic default factories."""

    return []


def _empty_restore_summaries() -> list["RancherRestoreSummary"]:
    """Return a typed empty restore-summary list for Pydantic default factories."""

    return []


class RancherBackupSummary(RancherModel):
    """Typed summary for one Rancher Backup Operator Backup."""

    name: str = Field(
        default="<unknown-backup>",
        validation_alias=AliasPath("metadata", "name"),
    )
    encryption_config_secret_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "encryptionConfigSecretName"),
    )
    resource_set_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "resourceSetName"),
    )
    schedule: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "schedule"),
    )
    retention_count: int | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "retentionCount"),
    )
    backup_filename: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "filename"),
    )
    last_backup_time: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "lastBackupTs"),
    )
    summary_state: str | None = None


class RancherBackupDetail(RancherBackupSummary):
    """Typed detail for one Rancher Backup Operator Backup."""

    storage_location_summary: str | None = None
    condition_types_true: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherBackupList(RancherModel):
    """Typed list response for Rancher Backup Operator backups."""

    instance: str
    cluster_id: str
    backup_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    backups: list[RancherBackupSummary] = Field(default_factory=_empty_backup_summaries)


class RancherRestoreSummary(RancherModel):
    """Typed summary for one Rancher Backup Operator Restore."""

    name: str = Field(
        default="<unknown-restore>",
        validation_alias=AliasPath("metadata", "name"),
    )
    backup_filename: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "backupFilename"),
    )
    encryption_config_secret_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "encryptionConfigSecretName"),
    )
    prune_value: bool | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "prune"),
    )
    summary_state: str | None = None
    restore_completion_ts: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "restoreCompletionTs"),
    )


class RancherRestoreDetail(RancherRestoreSummary):
    """Typed detail for one Rancher Backup Operator Restore."""

    storage_location_summary: str | None = None
    condition_types_true: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherRestoreList(RancherModel):
    """Typed list response for Rancher Backup Operator restores."""

    instance: str
    cluster_id: str
    restore_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    restores: list[RancherRestoreSummary] = Field(default_factory=_empty_restore_summaries)
