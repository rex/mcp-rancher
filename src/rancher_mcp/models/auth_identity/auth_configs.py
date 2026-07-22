"""Auth-config models for curated Rancher auth and identity tools."""

from pydantic import Field

from rancher_mcp.models.auth_identity.common import empty_strings
from rancher_mcp.models.base import RancherModel


def _empty_auth_configs() -> list["RancherAuthConfigSummary"]:
    """Return a typed empty auth-config list for default factories."""

    return []


class RancherAuthConfigSummary(RancherModel):
    """Typed summary for one Rancher auth config."""

    id: str = "<unknown-auth-config>"
    name: str = "<unknown-auth-config>"
    provider_type: str | None = Field(default=None, validation_alias="type")
    enabled: bool | None = None
    access_mode: str | None = Field(default=None, validation_alias="accessMode")


class RancherAuthConfigDetail(RancherAuthConfigSummary):
    """Typed detail for one Rancher auth config."""

    created: str | None = None
    created_ts: int | None = Field(default=None, validation_alias="createdTS")
    creator_id: str | None = Field(default=None, validation_alias="creatorId")
    allowed_principal_ids: list[str] = Field(
        default_factory=empty_strings,
        validation_alias="allowedPrincipalIds",
    )
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherAuthConfigList(RancherModel):
    """Typed list response for Rancher auth configs."""

    instance: str
    auth_config_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    auth_configs: list[RancherAuthConfigSummary] = Field(default_factory=_empty_auth_configs)
