"""Role-template models for curated Rancher RBAC tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.rbac.common import RancherPolicyRule, empty_rules, empty_strings


def _empty_role_templates() -> list["RancherRoleTemplateSummary"]:
    """Return a typed empty role-template list for default factories."""

    return []


class RancherRoleTemplateSummary(RancherModel):
    """Typed summary for one Rancher role template."""

    id: str = "<unknown-role-template>"
    name: str = "<unknown-role-template>"
    description: str | None = None
    builtin: bool | None = None
    context: str | None = None
    administrative: bool | None = None
    cluster_creator_default: bool | None = None
    project_creator_default: bool | None = None
    external: bool | None = None
    hidden: bool | None = None
    locked: bool | None = None
    inherited_role_template_ids: list[str] = Field(
        default_factory=empty_strings,
        validation_alias="roleTemplateIds",
    )


class RancherRoleTemplateDetail(RancherRoleTemplateSummary):
    """Typed detail for one Rancher role template."""

    created: str | None = None
    created_ts: int | None = None
    creator_id: str | None = None
    rules: list[RancherPolicyRule] = Field(default_factory=empty_rules)
    rule_count: int = 0
    inherited_role_template_count: int = 0
    link_keys: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherRoleTemplateList(RancherModel):
    """Typed list response for Rancher role templates."""

    instance: str
    role_template_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    role_templates: list[RancherRoleTemplateSummary] = Field(default_factory=_empty_role_templates)
