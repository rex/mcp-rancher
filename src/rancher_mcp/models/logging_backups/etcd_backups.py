"""Etcd-backup models for curated Rancher backup tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def _empty_etcd_backups() -> list["RancherEtcdBackupSummary"]:
    """Return a typed empty etcd-backup list for default factories."""

    return []


class RancherEtcdBackupSummary(RancherModel):
    """Typed summary for one Rancher etcd backup."""

    id: str = "<unknown-etcd-backup>"
    name: str = "<unknown-etcd-backup>"
    cluster_id: str | None = None
    namespace_id: str | None = None
    filename: str | None = None
    manual: bool | None = None
    state: str | None = None
    transitioning: str | None = None
    transitioning_message: str | None = None


class RancherEtcdBackupDetail(RancherEtcdBackupSummary):
    """Typed detail for one Rancher etcd backup."""

    backup_config: dict[str, object] = Field(default_factory=dict)
    status: dict[str, object] = Field(default_factory=dict)
    status_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherEtcdBackupList(RancherModel):
    """Typed list response for Rancher etcd backups."""

    instance: str
    cluster_id: str | None = None
    """Echoes the `cluster_id` list filter when one was passed (None means
    "all clusters") — so `next_steps` (models/base.py) can propagate a real
    scope to cluster-scoped next-step tools instead of silently defaulting."""
    etcd_backup_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    etcd_backups: list[RancherEtcdBackupSummary] = Field(default_factory=_empty_etcd_backups)
