"""Pydantic descriptor schema for curated tool codegen.

A descriptor is the YAML at `catalog/curated_tools/<id>.yml`. It captures
the mechanical shape of a curated tool pack so the generator can emit
the full plumbing without per-type Python files.

Editorial pieces (output Pydantic models, normalization helpers, tool
descriptions, next-step hints) are referenced from the descriptor but
remain hand-written. The generator imports them; it does not produce
them.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Plane = Literal["norman", "steve"]
Transport = Literal["steve", "k8s-proxy", "norman"]
Operation = Literal["list", "get", "create", "apply", "patch", "delete"]
AnnotationSet = Literal[
    "READ_ONLY",
    "SAFE_WRITE",
    "IDEMPOTENT_WRITE",
    "DESTRUCTIVE",
    "UNKNOWN_ACTION",
]
FilterType = Literal["str", "bool"]
FilterPredicate = Literal["is_provided", "is_true"]


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


class ToolMeta(BaseModel):
    """MCP tool metadata for one operation."""

    model_config = ConfigDict(extra="forbid")

    name: str
    """Public MCP tool name (e.g. `rancher_pods_list`)."""

    description: str
    """One-line tool description shown to the LLM."""

    annotation_set: AnnotationSet = "READ_ONLY"
    """Named ToolAnnotations constant from `tools.support.annotations`."""


class ToolsBlock(BaseModel):
    """Per-operation MCP tool metadata."""

    model_config = ConfigDict(extra="forbid")

    list_: ToolMeta | None = Field(default=None, alias="list")
    get: ToolMeta | None = None
    create: ToolMeta | None = None
    apply: ToolMeta | None = None
    patch: ToolMeta | None = None
    delete: ToolMeta | None = None


class Descriptor(BaseModel):
    """One curated tool descriptor."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(default=1)

    # --- Identity --------------------------------------------------

    id: str
    """Descriptor id; matches filename stem under catalog/curated_tools/."""

    pack: str
    """Target package directory under `src/rancher_mcp/tools/`."""

    display_name_singular: str
    """Used in docstrings (e.g. "pod" -> "Fetch and normalize one pod.")."""

    display_name_plural: str
    """Used in docstrings (e.g. "pods" -> "the pods collection")."""

    # --- API plane and paths ---------------------------------------

    plane: Plane
    """Rancher API plane: `norman` (/v3) or `steve` (/v1)."""

    transport: Transport = "steve"
    """Which client + path style. `steve` = SteveDiscoveryClient + URL templates.
    `k8s-proxy` = ManagementDiscoveryClient + path-helper functions (used for
    workload controllers on Rancher 2.6.5 where Steve write paths are unreliable).
    `norman` = ManagementDiscoveryClient + Norman /v3 URL templates with `data_items`
    payload extractor.
    """

    namespaced: bool = True
    """Whether the resource is namespaced. Affects path templating."""

    cluster_id_required: bool = True
    """If True (default), the public list/get signatures take `cluster_id: str = "local"`
    and the fetch helpers/clients receive it. Set False for Rancher-global Norman
    resources (e.g. settings, features, RBAC roles) that have no cluster context."""

    pagination: bool = True
    """If True (default), generate cursor pagination plumbing (`page_token` parameter,
    `next_page_token` field on the list model, `next_page_token_from_payload` import).
    Set False for legacy Norman packs without pagination support."""

    list_path: str = ""
    """List path template (e.g. `/pods/{namespace}`). Required when transport=steve.
    Ignored when transport=k8s-proxy (paths come from path_helper)."""

    detail_path: str = ""
    """Detail path template (e.g. `/pods/{namespace}/{pod_name}`). Required when
    transport=steve. Ignored when transport=k8s-proxy."""

    path_helper: PathHelper | None = None
    """Path-helper config for transport=k8s-proxy. Must be None for transport=steve."""

    # --- Models (full import paths) --------------------------------

    list_response_model: str
    """Full import path to list response model class."""

    detail_response_model: str
    """Full import path to detail response model class."""

    # --- Shared imports from tools/<pack>/shared.py ----------------

    shared_imports: list[str] = []
    """Names imported from `tools.<pack>.shared` (e.g. `data_items`)."""

    support_value_imports: list[str] = []
    """Extra names imported from `tools.support.values` beyond `mapping_value`
    (e.g. `string_dict` for annotation extraction)."""

    summary_function: str
    """Name of the summary normalizer function (e.g. `pod_summary_from_payload`)."""

    query_builder_function: str = "build_steve_list_query_params"
    """Name of the query-param builder function. Default lives in
    `rancher_mcp.services.resource_queries`. Override when a pack uses a
    pack-specific builder (then set `query_builder_in_shared` to True)."""

    query_builder_in_shared: bool = False
    """If True, import `query_builder_function` from `tools.<pack>.shared`
    instead of `services.resource_queries`."""

    # --- Operations to generate ------------------------------------

    operations: list[Operation]
    """Which operations to generate code for."""

    # --- Per-operation config --------------------------------------

    list_: ListConfig | None = Field(default=None, alias="list")
    get: GetConfig | None = None

    # --- MCP tool metadata -----------------------------------------

    tools: ToolsBlock

    # --- Validation ------------------------------------------------

    @field_validator("id", "pack")
    @classmethod
    def _identifier_only(cls, value: str) -> str:
        if not value.replace("_", "").isalnum():
            raise ValueError(f"must be alphanumeric (with underscores): {value!r}")
        return value

    @model_validator(mode="after")
    def _check_consistency(self) -> Descriptor:
        if "list" in self.operations and self.list_ is None:
            raise ValueError("operations includes 'list' but list config is missing")
        if "get" in self.operations and self.get is None:
            raise ValueError("operations includes 'get' but get config is missing")
        if "list" in self.operations and self.tools.list_ is None:
            raise ValueError("operations includes 'list' but tools.list metadata is missing")
        if "get" in self.operations and self.tools.get is None:
            raise ValueError("operations includes 'get' but tools.get metadata is missing")
        if self.transport == "steve":
            if not self.list_path:
                raise ValueError("transport=steve requires list_path")
            if not self.detail_path:
                raise ValueError("transport=steve requires detail_path")
            if self.path_helper is not None:
                raise ValueError("transport=steve must not set path_helper")
            if self.namespaced and "{namespace}" not in self.list_path:
                raise ValueError("namespaced=true requires {namespace} in list_path")
            if self.namespaced and "{namespace}" not in self.detail_path:
                raise ValueError("namespaced=true requires {namespace} in detail_path")
        elif self.transport == "k8s-proxy":
            if self.path_helper is None:
                raise ValueError("transport=k8s-proxy requires path_helper")
            if self.list_path or self.detail_path:
                raise ValueError(
                    "transport=k8s-proxy must not set list_path/detail_path; "
                    "use path_helper instead"
                )
        elif self.transport == "norman":
            if not self.list_path:
                raise ValueError("transport=norman requires list_path")
            if not self.detail_path:
                raise ValueError("transport=norman requires detail_path")
            if self.path_helper is not None:
                raise ValueError("transport=norman must not set path_helper")
        if (
            self.cluster_id_required
            and self.list_ is not None
            and "cluster_id" in self.list_.query_params
        ):
            raise ValueError(
                "cluster_id_required=true conflicts with cluster_id in "
                "list.query_params (would generate two parameters named cluster_id). "
                "Set cluster_id_required=false (Norman global resources with cluster filter) "
                "or remove cluster_id from query_params (Steve/k8s-proxy with path arg)."
            )
        return self


class PackDescriptor(BaseModel):
    """Pack-level metadata, one per package directory under tools/."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=1)

    id: str
    """Pack id; matches a package directory name under `src/rancher_mcp/tools/`."""

    register_function: str
    """Name of the register function exposed in the pack `__init__.py`."""

    docstring: str
    """Module docstring for the pack `__init__.py`."""

    register_docstring: str
    """Docstring used inside the register function body."""

    @field_validator("id")
    @classmethod
    def _identifier_only(cls, value: str) -> str:
        if not value.replace("_", "").isalnum():
            raise ValueError(f"must be alphanumeric (with underscores): {value!r}")
        return value


def load_descriptor(path: Path) -> Descriptor:
    """Load and validate one per-resource descriptor file."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"{path}: top-level YAML must be a mapping")
    return Descriptor.model_validate(cast(Mapping[str, object], raw))


def load_pack_descriptor(path: Path) -> PackDescriptor:
    """Load and validate one pack-level metadata file."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"{path}: top-level YAML must be a mapping")
    return PackDescriptor.model_validate(cast(Mapping[str, object], raw))


def load_all_descriptors(directory: Path) -> list[Descriptor]:
    """Load every per-resource descriptor under the given directory."""

    descriptor_files = [p for p in directory.glob("*.yml") if not p.name.startswith("_")]
    return sorted(
        (load_descriptor(p) for p in descriptor_files),
        key=lambda d: (d.pack, d.id),
    )


def load_all_pack_descriptors(directory: Path) -> dict[str, PackDescriptor]:
    """Load every pack-level metadata file under directory/_packs/."""

    packs_dir = directory / "_packs"
    if not packs_dir.is_dir():
        return {}
    return {pack.id: pack for pack in (load_pack_descriptor(p) for p in packs_dir.glob("*.yml"))}
