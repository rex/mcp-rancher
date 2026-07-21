"""Fleet-workspace models for curated Rancher Fleet tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def _empty_fleet_workspaces() -> list["RancherFleetWorkspaceSummary"]:
    """Return a typed empty Fleet workspace list for default factories."""

    return []


class RancherFleetWorkspaceSummary(RancherModel):
    """Typed summary for one Rancher Fleet workspace."""

    id: str = "<unknown-fleet-workspace>"
    name: str = "<unknown-fleet-workspace>"


class RancherFleetWorkspaceDetail(RancherFleetWorkspaceSummary):
    """Typed detail for one Rancher Fleet workspace."""

    created: str | None = None
    created_ts: int | None = None
    creator_id: str | None = None
    status: dict[str, object] = Field(default_factory=dict)
    status_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherFleetWorkspaceList(RancherModel):
    """Typed list response for Rancher Fleet workspaces."""

    instance: str
    fleet_workspace_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    fleet_workspaces: list[RancherFleetWorkspaceSummary] = Field(
        default_factory=_empty_fleet_workspaces
    )
