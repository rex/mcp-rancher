"""Group models for curated Rancher auth and identity tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def _empty_groups() -> list["RancherGroupSummary"]:
    """Return a typed empty group list for default factories."""

    return []


class RancherGroupSummary(RancherModel):
    """Typed summary for one Rancher group."""

    id: str = "<unknown-group>"
    name: str = "<unknown-group>"
    principal_type: str | None = Field(default=None, validation_alias="principalType")


class RancherGroupDetail(RancherGroupSummary):
    """Typed detail for one Rancher group."""

    created: str | None = None
    created_ts: int | None = Field(default=None, validation_alias="createdTS")
    creator_id: str | None = Field(default=None, validation_alias="creatorId")
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherGroupList(RancherModel):
    """Typed list response for Rancher groups."""

    instance: str
    group_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    groups: list[RancherGroupSummary] = Field(default_factory=_empty_groups)
