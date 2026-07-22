"""Global-role models for curated Rancher RBAC tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.rbac.common import RancherPolicyRule, empty_rules


def _empty_global_roles() -> list["RancherGlobalRoleSummary"]:
    """Return a typed empty global-role list for default factories."""

    return []


class RancherGlobalRoleSummary(RancherModel):
    """Typed summary for one Rancher global role."""

    id: str = "<unknown-global-role>"
    name: str = "<unknown-global-role>"
    description: str | None = None
    builtin: bool | None = None
    new_user_default: bool | None = None


class RancherGlobalRoleDetail(RancherGlobalRoleSummary):
    """Typed detail for one Rancher global role."""

    created: str | None = None
    created_ts: int | None = None
    creator_id: str | None = None
    rules: list[RancherPolicyRule] = Field(default_factory=empty_rules)
    rule_count: int = 0
    link_keys: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherGlobalRoleList(RancherModel):
    """Typed list response for Rancher global roles."""

    instance: str
    global_role_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    global_roles: list[RancherGlobalRoleSummary] = Field(default_factory=_empty_global_roles)
