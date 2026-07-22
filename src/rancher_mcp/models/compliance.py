"""Typed models for Rancher CIS compliance tools."""

from __future__ import annotations

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_profiles() -> list[RancherCisScanProfileSummary]:
    return []


def _empty_scans() -> list[RancherCisScanSummary]:
    return []


class RancherCisScanProfileSummary(RancherModel):
    """Typed summary for one CIS scan profile."""

    id: str = "<unknown-profile>"
    name: str = "<unknown-profile>"
    cluster_id: str | None = None
    cis_benchmark_version: str | None = None
    state: str | None = None


def _empty_tests() -> list[dict[str, object]]:
    return []


class RancherCisScanProfileDetail(RancherCisScanProfileSummary):
    """Typed detail for one CIS scan profile."""

    tests: list[dict[str, object]] = Field(default_factory=_empty_tests)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherCisScanProfileList(RancherModel):
    """Typed list response for CIS scan profiles."""

    instance: str
    cluster_id: str | None = None
    """Echoes the `cluster_id` list filter when one was passed (None means
    "all clusters") — so `next_steps` (models/base.py) can propagate a real
    scope to cluster-scoped next-step tools instead of silently defaulting."""
    profile_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    profiles: list[RancherCisScanProfileSummary] = Field(default_factory=_empty_profiles)


class RancherCisScanSummary(RancherModel):
    """Typed summary for one CIS scan run."""

    id: str = "<unknown-scan>"
    name: str = "<unknown-scan>"
    cluster_id: str | None = None
    scan_profile_name: str | None = None
    state: str | None = None
    failed: int | None = None
    passed: int | None = None
    skipped: int | None = None
    total: int | None = None
    cron_schedule: str | None = Field(
        default=None,
        validation_alias=AliasPath("scheduledScanConfig", "cronSchedule"),
    )
    retention_count: int | None = Field(
        default=None,
        validation_alias=AliasPath("scheduledScanConfig", "retentionCount"),
    )


class RancherCisScanDetail(RancherCisScanSummary):
    """Typed detail for one CIS scan run."""

    status: dict[str, object] = Field(default_factory=dict)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherCisScanList(RancherModel):
    """Typed list response for CIS scan runs."""

    instance: str
    cluster_id: str | None = None
    """Echoes the `cluster_id` list filter when one was passed (None means
    "all clusters") — so `next_steps` (models/base.py) can propagate a real
    scope to cluster-scoped next-step tools instead of silently defaulting."""
    scan_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    scans: list[RancherCisScanSummary] = Field(default_factory=_empty_scans)
