"""Binding models for curated Rancher RBAC tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def _empty_global_role_bindings() -> list["RancherGlobalRoleBindingSummary"]:
    """Return a typed empty global-role-binding list for default factories."""

    return []


def _empty_cluster_role_template_bindings() -> list["RancherClusterRoleTemplateBindingSummary"]:
    """Return a typed empty cluster binding list for default factories."""

    return []


def _empty_project_role_template_bindings() -> list["RancherProjectRoleTemplateBindingSummary"]:
    """Return a typed empty project binding list for default factories."""

    return []


class RancherGlobalRoleBindingSummary(RancherModel):
    """Typed summary for one Rancher global role binding."""

    id: str = "<unknown-global-role-binding>"
    name: str = "<unknown-global-role-binding>"
    global_role_id: str | None = None
    user_id: str | None = None
    group_principal_id: str | None = None


class RancherGlobalRoleBindingDetail(RancherGlobalRoleBindingSummary):
    """Typed detail for one Rancher global role binding."""

    created: str | None = None
    created_ts: int | None = None
    creator_id: str | None = None
    subject_kind: str = "unknown"
    subject_id: str | None = None
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherClusterRoleTemplateBindingSummary(RancherModel):
    """Typed summary for one Rancher cluster role-template binding."""

    id: str = "<unknown-cluster-role-template-binding>"
    name: str = "<unknown-cluster-role-template-binding>"
    cluster_id: str | None = None
    namespace_id: str | None = None
    role_template_id: str | None = None
    user_id: str | None = None
    user_principal_id: str | None = None
    group_id: str | None = None
    group_principal_id: str | None = None


class RancherClusterRoleTemplateBindingDetail(RancherClusterRoleTemplateBindingSummary):
    """Typed detail for one Rancher cluster role-template binding."""

    created: str | None = None
    created_ts: int | None = None
    creator_id: str | None = None
    subject_kind: str = "unknown"
    subject_id: str | None = None
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherProjectRoleTemplateBindingSummary(RancherModel):
    """Typed summary for one Rancher project role-template binding."""

    id: str = "<unknown-project-role-template-binding>"
    name: str = "<unknown-project-role-template-binding>"
    project_id: str | None = None
    namespace_id: str | None = None
    role_template_id: str | None = None
    service_account: str | None = None
    user_id: str | None = None
    user_principal_id: str | None = None
    group_id: str | None = None
    group_principal_id: str | None = None


class RancherProjectRoleTemplateBindingDetail(RancherProjectRoleTemplateBindingSummary):
    """Typed detail for one Rancher project role-template binding."""

    created: str | None = None
    created_ts: int | None = None
    creator_id: str | None = None
    subject_kind: str = "unknown"
    subject_id: str | None = None
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherGlobalRoleBindingList(RancherModel):
    """Typed list response for Rancher global role bindings."""

    instance: str
    global_role_binding_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    global_role_bindings: list[RancherGlobalRoleBindingSummary] = Field(
        default_factory=_empty_global_role_bindings
    )


class RancherClusterRoleTemplateBindingList(RancherModel):
    """Typed list response for Rancher cluster role-template bindings."""

    instance: str
    cluster_role_template_binding_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    cluster_role_template_bindings: list[RancherClusterRoleTemplateBindingSummary] = Field(
        default_factory=_empty_cluster_role_template_bindings
    )


class RancherProjectRoleTemplateBindingList(RancherModel):
    """Typed list response for Rancher project role-template bindings."""

    instance: str
    project_role_template_binding_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    project_role_template_bindings: list[RancherProjectRoleTemplateBindingSummary] = Field(
        default_factory=_empty_project_role_template_bindings
    )
