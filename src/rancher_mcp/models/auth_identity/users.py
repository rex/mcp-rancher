"""User models for curated Rancher auth and identity tools."""

from pydantic import AliasPath, Field, field_validator

from rancher_mcp.models.auth_identity.common import (
    RancherCondition,
    empty_conditions,
    empty_strings,
)
from rancher_mcp.models.base import RancherModel


def _empty_users() -> list["RancherUserSummary"]:
    """Return a typed empty user list for default factories."""

    return []


class RancherUserSummary(RancherModel):
    """Typed summary for one Rancher user."""

    id: str = "<unknown-user>"
    name: str = "<unknown-user>"
    username: str | None = None
    enabled: bool | None = None
    me: bool | None = None
    must_change_password: bool | None = Field(default=None, validation_alias="mustChangePassword")
    state: str | None = None
    principal_ids: list[str] = Field(default_factory=empty_strings, validation_alias="principalIds")


class RancherUserDetail(RancherUserSummary):
    """Typed detail for one Rancher user."""

    description: str | None = None
    conditions: list[RancherCondition] = Field(
        default_factory=empty_conditions,
        validation_alias=AliasPath("conditions"),
    )
    condition_types_true: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)

    @field_validator("conditions", mode="before")
    @classmethod
    def _none_conditions_to_empty(cls, value: object) -> object:
        """Normalize null condition lists from Rancher to empty lists."""

        return [] if value is None else value


class RancherUserList(RancherModel):
    """Typed list response for Rancher users."""

    instance: str
    user_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    users: list[RancherUserSummary] = Field(default_factory=_empty_users)
