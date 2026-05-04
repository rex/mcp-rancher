"""Shared helpers for curated Rancher RBAC tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.rbac import (
    RancherClusterRoleTemplateBindingSummary,
    RancherGlobalRoleBindingSummary,
    RancherGlobalRoleSummary,
    RancherProjectRoleTemplateBindingSummary,
    RancherRoleTemplateSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import mapping_value


def _build_global_role_query_params(
    *,
    limit: int | None,
    builtin: bool | None,
    name: str | None,
    new_user_default: bool | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher global-roles collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if builtin is not None:
        params["builtin"] = builtin
    if name is not None:
        params["name"] = name
    if new_user_default is not None:
        params["newUserDefault"] = new_user_default
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_role_template_query_params(
    *,
    limit: int | None,
    builtin: bool | None,
    context: str | None,
    administrative: bool | None,
    cluster_creator_default: bool | None,
    project_creator_default: bool | None,
    external: bool | None,
    hidden: bool | None,
    locked: bool | None,
    name: str | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher role-templates collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if builtin is not None:
        params["builtin"] = builtin
    if context is not None:
        params["context"] = context
    if administrative is not None:
        params["administrative"] = administrative
    if cluster_creator_default is not None:
        params["clusterCreatorDefault"] = cluster_creator_default
    if project_creator_default is not None:
        params["projectCreatorDefault"] = project_creator_default
    if external is not None:
        params["external"] = external
    if hidden is not None:
        params["hidden"] = hidden
    if locked is not None:
        params["locked"] = locked
    if name is not None:
        params["name"] = name
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_global_role_binding_query_params(
    *,
    limit: int | None,
    global_role_id: str | None,
    user_id: str | None,
    group_principal_id: str | None,
    name: str | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher global-role-bindings collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if global_role_id is not None:
        params["globalRoleId"] = global_role_id
    if user_id is not None:
        params["userId"] = user_id
    if group_principal_id is not None:
        params["groupPrincipalId"] = group_principal_id
    if name is not None:
        params["name"] = name
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_cluster_role_template_binding_query_params(
    *,
    limit: int | None,
    cluster_id: str | None,
    role_template_id: str | None,
    user_id: str | None,
    user_principal_id: str | None,
    group_id: str | None,
    group_principal_id: str | None,
    namespace_id: str | None,
    name: str | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the cluster role-template-bindings collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if role_template_id is not None:
        params["roleTemplateId"] = role_template_id
    if user_id is not None:
        params["userId"] = user_id
    if user_principal_id is not None:
        params["userPrincipalId"] = user_principal_id
    if group_id is not None:
        params["groupId"] = group_id
    if group_principal_id is not None:
        params["groupPrincipalId"] = group_principal_id
    if namespace_id is not None:
        params["namespaceId"] = namespace_id
    if name is not None:
        params["name"] = name
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_project_role_template_binding_query_params(
    *,
    limit: int | None,
    project_id: str | None,
    role_template_id: str | None,
    user_id: str | None,
    user_principal_id: str | None,
    group_id: str | None,
    group_principal_id: str | None,
    namespace_id: str | None,
    service_account: str | None,
    name: str | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the project role-template-bindings collection."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if project_id is not None:
        params["projectId"] = project_id
    if role_template_id is not None:
        params["roleTemplateId"] = role_template_id
    if user_id is not None:
        params["userId"] = user_id
    if user_principal_id is not None:
        params["userPrincipalId"] = user_principal_id
    if group_id is not None:
        params["groupId"] = group_id
    if group_principal_id is not None:
        params["groupPrincipalId"] = group_principal_id
    if namespace_id is not None:
        params["namespaceId"] = namespace_id
    if service_account is not None:
        params["serviceAccount"] = service_account
    if name is not None:
        params["name"] = name
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher list payload."""

    return object_items(payload, field="data")


def _action_keys(payload: Mapping[str, object]) -> list[str]:
    """Return sorted Rancher action keys from a payload."""

    return sorted(mapping_value(payload, "actions") or {})


def _link_keys(payload: Mapping[str, object]) -> list[str]:
    """Return sorted Rancher link keys from a payload."""

    return sorted(mapping_value(payload, "links") or {})


def _global_role_summary_from_payload(payload: Mapping[str, object]) -> RancherGlobalRoleSummary:
    """Normalize one Rancher global-role payload."""

    return RancherGlobalRoleSummary.model_validate(payload)


def _role_template_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherRoleTemplateSummary:
    """Normalize one Rancher role-template payload."""

    return RancherRoleTemplateSummary.model_validate(payload)


def _global_role_binding_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherGlobalRoleBindingSummary:
    """Normalize one Rancher global-role-binding payload."""

    return RancherGlobalRoleBindingSummary.model_validate(payload)


def _cluster_role_template_binding_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherClusterRoleTemplateBindingSummary:
    """Normalize one Rancher cluster role-template-binding payload."""

    return RancherClusterRoleTemplateBindingSummary.model_validate(payload)


def _project_role_template_binding_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherProjectRoleTemplateBindingSummary:
    """Normalize one Rancher project role-template-binding payload."""

    return RancherProjectRoleTemplateBindingSummary.model_validate(payload)


def _binding_subject(payload: Mapping[str, object]) -> tuple[str, str | None]:
    """Derive the primary RBAC subject kind and id from a binding payload."""

    for subject_kind, key in (
        ("user", "userId"),
        ("user_principal", "userPrincipalId"),
        ("group", "groupId"),
        ("group_principal", "groupPrincipalId"),
        ("service_account", "serviceAccount"),
    ):
        subject_id = payload.get(key)
        if isinstance(subject_id, str) and subject_id:
            return subject_kind, subject_id
    return "unknown", None


action_keys = _action_keys
binding_subject = _binding_subject
build_cluster_role_template_binding_query_params = _build_cluster_role_template_binding_query_params
build_global_role_binding_query_params = _build_global_role_binding_query_params
build_global_role_query_params = _build_global_role_query_params
build_project_role_template_binding_query_params = _build_project_role_template_binding_query_params
build_role_template_query_params = _build_role_template_query_params
cluster_role_template_binding_summary_from_payload = (
    _cluster_role_template_binding_summary_from_payload
)
data_items = _data_items
global_role_binding_summary_from_payload = _global_role_binding_summary_from_payload
global_role_summary_from_payload = _global_role_summary_from_payload
link_keys = _link_keys
project_role_template_binding_summary_from_payload = (
    _project_role_template_binding_summary_from_payload
)
role_template_summary_from_payload = _role_template_summary_from_payload
