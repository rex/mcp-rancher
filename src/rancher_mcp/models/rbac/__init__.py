"""Curated Rancher RBAC models."""

from rancher_mcp.models.rbac.bindings import (
    RancherClusterRoleTemplateBindingDetail,
    RancherClusterRoleTemplateBindingList,
    RancherClusterRoleTemplateBindingSummary,
    RancherGlobalRoleBindingDetail,
    RancherGlobalRoleBindingList,
    RancherGlobalRoleBindingSummary,
    RancherProjectRoleTemplateBindingDetail,
    RancherProjectRoleTemplateBindingList,
    RancherProjectRoleTemplateBindingSummary,
)
from rancher_mcp.models.rbac.common import RancherPolicyRule
from rancher_mcp.models.rbac.global_roles import (
    RancherGlobalRoleDetail,
    RancherGlobalRoleList,
    RancherGlobalRoleSummary,
)
from rancher_mcp.models.rbac.role_templates import (
    RancherRoleTemplateDetail,
    RancherRoleTemplateList,
    RancherRoleTemplateSummary,
)

__all__ = [
    "RancherClusterRoleTemplateBindingDetail",
    "RancherClusterRoleTemplateBindingList",
    "RancherClusterRoleTemplateBindingSummary",
    "RancherGlobalRoleBindingDetail",
    "RancherGlobalRoleBindingList",
    "RancherGlobalRoleBindingSummary",
    "RancherGlobalRoleDetail",
    "RancherGlobalRoleList",
    "RancherGlobalRoleSummary",
    "RancherPolicyRule",
    "RancherProjectRoleTemplateBindingDetail",
    "RancherProjectRoleTemplateBindingList",
    "RancherProjectRoleTemplateBindingSummary",
    "RancherRoleTemplateDetail",
    "RancherRoleTemplateList",
    "RancherRoleTemplateSummary",
]
