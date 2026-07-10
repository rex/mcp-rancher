"""List / get read-path config models and the shared arg spec.

These describe the read operations (list, get) plus `ArgSpec`, the typed
input argument reused by every write operation in `operations.py`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .aliases import ArgType, FilterPredicate, FilterType


class FilterSpec(BaseModel):
    """A post-fetch client-side filter on the list response."""

    model_config = ConfigDict(extra="forbid")

    name: str
    """Tool argument name (also the local variable name)."""

    summary_field: str
    """Attribute on the summary model to compare against."""

    type: FilterType = "str"
    """Filter value type. `bool` uses `is`, `str` uses `==`."""

    predicate: FilterPredicate = "is_provided"
    """When the filter is applied. `is_provided` (default): `if X is not None`.
    `is_true`: `if X is True` (only filters when explicitly True)."""


class PathHelper(BaseModel):
    """Path-helper functions for transports that don't use simple URL templates.

    Used by `transport: k8s-proxy` to call helpers like
    `workload_collection_path(cluster_id, namespace, "deployments")`.
    """

    model_config = ConfigDict(extra="forbid")

    module: str
    """Full import path to the module containing the helpers."""

    list_function: str
    """Function name for the list collection path."""

    detail_function: str
    """Function name for the detail resource path."""

    resource_kind: str | None = None
    """If set, passed as a string-literal positional arg to both helpers
    (e.g. `"deployments"` for the workloads path helper). Omit for helpers
    pre-bound to one resource (e.g. `storage_class_collection_path`)."""


class ListConfig(BaseModel):
    """List operation configuration."""

    model_config = ConfigDict(extra="forbid")

    query_params: list[
        Literal[
            # Steve / k8s-proxy params
            "limit",
            "label_selector",
            "field_selector",
            "continue_token",
            # Norman params
            "state",
            "source",
            "customized",
            "enabled",
            "sort_by",
            "reverse",
            "marker",
            "cluster_id",
            "me",
            "name",
            "provider_type",
            "access_mode",
            "severity",
            "kind",
            "helm_version",
            "catalog_id",
            "category",
            "project_id",
            "external_id",
            "version",
            "version_name",
            # rbac
            "builtin",
            "new_user_default",
            "context",
            "administrative",
            "cluster_creator_default",
            "project_creator_default",
            "external",
            "hidden",
            "locked",
            "global_role_id",
            "role_template_id",
            "user_id",
            "user_principal_id",
            "group_id",
            "group_principal_id",
            "namespace_id",
            "service_account",
            # logging_backups
            "enable_json_parsing",
            "include_system_component",
            "output_flush_interval",
            "manual",
            "filename",
            # clusters_nodes
            "role",
            "unschedulable",
            # provisioning
            "active",
            "driver",
            "cloud_credential_id",
        ]
    ]
    """Query-builder kwargs to pass through. Type for each is registered in
    `scripts/codegen/plan.QP_TYPES` and the kwarg name in `QP_KWARGS`."""

    filters: list[FilterSpec] = []
    """Post-fetch filters applied client-side after fetch."""

    count_field: str
    """Field on list response model holding the count (e.g. `pod_count`)."""

    collection_field: str
    """Field on list response model holding the items (e.g. `pods`)."""

    next_steps: list[str] = []
    """Suggested next-step tool names included in the list response."""


class DetailExtra(BaseModel):
    """An extra computed value passed into the detail model copy update.

    The expression renders as inline Python; the descriptor author owns
    the expression. Local variable names declared in `detail_locals` are
    in scope.
    """

    model_config = ConfigDict(extra="forbid")

    field: str
    """Update key on the detail model (e.g. `relationship_types`)."""

    expression: str
    """Python expression to assign (e.g. `relationship_types(metadata)`)."""


class DetailLocal(BaseModel):
    """A local variable extracted before the detail model copy update."""

    model_config = ConfigDict(extra="forbid")

    name: str
    """Local variable name (e.g. `metadata`)."""

    expression: str
    """Python expression to assign (e.g. `mapping_value(payload, "metadata") or {}`)."""


class GetConfig(BaseModel):
    """Get operation configuration."""

    model_config = ConfigDict(extra="forbid")

    arg_name: str
    """Second positional arg name for namespaced gets (e.g. `pod_name`)."""

    summary_copy_fields: list[str]
    """Summary attributes copied as `summary.X` into the model_copy update."""

    locals: list[DetailLocal] = []
    """Local variables computed before the detail update."""

    extras: list[DetailExtra] = []
    """Additional computed update keys."""

    include_link_keys: bool = True
    """Add `link_keys: sorted(mapping_value(payload, "links") or {})`."""

    include_action_keys: bool = False
    """Add `action_keys: sorted(mapping_value(payload, "actions") or {})`.
    Norman responses include an `actions` field for invokable resource actions
    (e.g. `setpassword` on user, `disable` on auth_config); leave False for
    Steve / k8s-proxy resources where this field is absent."""

    include_payload: bool = True
    """Add `payload: dict(payload)`."""

    next_steps: list[str] = []
    """Suggested next-step tool names included in the detail response."""


class ArgSpec(BaseModel):
    """One typed input argument to a write operation.

    Resource name and namespace are NOT declared via ArgSpec — they are
    auto-injected by codegen using `get.arg_name` and the descriptor's
    `namespaced` flag. ArgSpec only describes the body args (data,
    replicas, image, labels, etc.).
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    """Public arg name on the generated tool (e.g. `data`, `replicas`).
    Must match the keyword the payload composer accepts."""

    type: ArgType
    """Python type to render in the function signature.
    `dict_str_str` → `dict[str, str]`, `dict_str_object` → `dict[str, object]`,
    `string_list` → `list[str]`."""

    required: bool = False
    """If True, no default; agent must provide. If False, the generated
    signature gives the arg `None` as default and the composer is
    responsible for handling it (typically by omitting the field from
    the payload when None)."""

    description: str = ""
    """Optional descriptive text. Reserved for future MCP input-schema
    surfacing — currently unused by codegen."""
