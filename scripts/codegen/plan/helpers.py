"""Static lookup tables and stateless helpers for plan building.

`QP_TYPES` / `QP_KWARGS` map descriptor query-param names to Python
types and builder kwargs; `ARG_TYPES_PYTHON` maps `ArgSpec.type` literals
to annotation strings. The `qp_type` / `qp_kwarg` / `arg_python_type`
accessors are exposed to Jinja as globals by the emitter.
"""

from __future__ import annotations

from collections.abc import Mapping

QP_TYPES: Mapping[str, str] = {
    # Steve / k8s-proxy
    "limit": "int",
    "label_selector": "str",
    "field_selector": "str",
    "continue_token": "str",
    # Norman
    "state": "str",
    "source": "str",
    "customized": "bool",
    "enabled": "bool",
    "sort_by": "str",
    "reverse": "bool",
    "marker": "str",
    "cluster_id": "str",
    "me": "bool",
    "severity": "str",
    "name": "str",
    "provider_type": "str",
    "access_mode": "str",
    # apps_catalogs
    "kind": "str",
    "helm_version": "str",
    "catalog_id": "str",
    "category": "str",
    "project_id": "str",
    "external_id": "str",
    "version": "str",
    "version_name": "str",
    # rbac
    "builtin": "bool",
    "new_user_default": "bool",
    "context": "str",
    "administrative": "bool",
    "cluster_creator_default": "bool",
    "project_creator_default": "bool",
    "external": "bool",
    "hidden": "bool",
    "locked": "bool",
    "global_role_id": "str",
    "role_template_id": "str",
    "user_id": "str",
    "user_principal_id": "str",
    "group_id": "str",
    "group_principal_id": "str",
    "namespace_id": "str",
    "service_account": "str",
    # logging_backups
    "enable_json_parsing": "bool",
    "include_system_component": "bool",
    "output_flush_interval": "int",
    "manual": "bool",
    "filename": "str",
    # clusters_nodes
    "role": "str",
    "unschedulable": "bool",
    # provisioning
    "active": "bool",
    "driver": "str",
    "cloud_credential_id": "str",
}

QP_KWARGS: Mapping[str, str] = {
    # Steve / k8s-proxy
    "limit": "limit",
    "label_selector": "label_selector",
    "field_selector": "field_selector",
    "continue_token": "continue_token",
    # Norman: kwarg names match the descriptor names; the pack-local builder
    # is responsible for mapping kwargs to HTTP query param names (e.g.
    # `sort_by` → `sort`, `enabled` → `value`).
    "state": "state",
    "source": "source",
    "customized": "customized",
    "enabled": "enabled",
    "sort_by": "sort_by",
    "reverse": "reverse",
    "marker": "marker",
    "cluster_id": "cluster_id",
    "me": "me",
    "severity": "severity",
    "name": "name",
    "provider_type": "provider_type",
    "access_mode": "access_mode",
    # apps_catalogs
    "kind": "kind",
    "helm_version": "helm_version",
    "catalog_id": "catalog_id",
    "category": "category",
    "project_id": "project_id",
    "external_id": "external_id",
    "version": "version",
    "version_name": "version_name",
    # rbac
    "builtin": "builtin",
    "new_user_default": "new_user_default",
    "context": "context",
    "administrative": "administrative",
    "cluster_creator_default": "cluster_creator_default",
    "project_creator_default": "project_creator_default",
    "external": "external",
    "hidden": "hidden",
    "locked": "locked",
    "global_role_id": "global_role_id",
    "role_template_id": "role_template_id",
    "user_id": "user_id",
    "user_principal_id": "user_principal_id",
    "group_id": "group_id",
    "group_principal_id": "group_principal_id",
    "namespace_id": "namespace_id",
    "service_account": "service_account",
    # logging_backups
    "enable_json_parsing": "enable_json_parsing",
    "include_system_component": "include_system_component",
    "output_flush_interval": "output_flush_interval",
    "manual": "manual",
    "filename": "filename",
    # clusters_nodes
    "role": "role",
    "unschedulable": "unschedulable",
    # provisioning
    "active": "active",
    "driver": "driver",
    "cloud_credential_id": "cloud_credential_id",
}


def qp_type(name: str) -> str:
    """Return the Python type for a Steve query-param kwarg."""

    return QP_TYPES[name]


def qp_kwarg(name: str) -> str:
    """Return the build_steve_list_query_params kwarg name for a query param."""

    return QP_KWARGS[name]


ARG_TYPES_PYTHON: Mapping[str, str] = {
    "str": "str",
    "int": "int",
    "bool": "bool",
    "dict_str_str": "dict[str, str]",
    "dict_str_object": "dict[str, object]",
    "string_list": "list[str]",
}


def arg_python_type(arg_type: str) -> str:
    """Return the Python type-annotation string for an ArgSpec.type literal."""

    return ARG_TYPES_PYTHON[arg_type]


def split_model_path(full_path: str) -> tuple[str, str]:
    """Split `pkg.subpkg.ClassName` → (`pkg.subpkg`, `ClassName`)."""

    module, _, name = full_path.rpartition(".")
    return module, name
