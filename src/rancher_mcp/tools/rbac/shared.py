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


def _build_query_params(**values: str | int | bool | None) -> dict[str, str | int | bool]:
    """Drop unset query params while preserving typed scalar values."""

    params: dict[str, str | int | bool] = {}
    for key, value in values.items():
        if value is not None:
            params[key] = value
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


build_query_params = _build_query_params
data_items = _data_items
action_keys = _action_keys
link_keys = _link_keys
binding_subject = _binding_subject
global_role_summary_from_payload = _global_role_summary_from_payload
role_template_summary_from_payload = _role_template_summary_from_payload
global_role_binding_summary_from_payload = _global_role_binding_summary_from_payload
cluster_role_template_binding_summary_from_payload = (
    _cluster_role_template_binding_summary_from_payload
)
project_role_template_binding_summary_from_payload = (
    _project_role_template_binding_summary_from_payload
)
