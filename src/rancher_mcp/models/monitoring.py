"""Typed models for Rancher monitoring status tools."""

from __future__ import annotations

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def _empty_conditions() -> list[dict[str, object]]:
    return []


class RancherMonitoringStatus(RancherModel):
    """Aggregated monitoring status for one Rancher cluster."""

    instance: str
    cluster_id: str
    monitoring_enabled: bool = False
    state: str | None = None
    grafana_endpoint: str | None = None
    prometheus_endpoint: str | None = None
    conditions: list[dict[str, object]] = Field(default_factory=_empty_conditions)
    payload: dict[str, object] = Field(default_factory=dict)
