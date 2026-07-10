"""Top-level descriptor models: `Descriptor` and `PackDescriptor`.

These aggregate the per-operation config models plus the cross-field
consistency validation that ties operations to their configs and tool
metadata.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .aliases import Operation, Plane, Transport
from .configs import GetConfig, ListConfig, PathHelper
from .operations import ApplyConfig, CreateConfig, DeleteConfig, PatchConfig, ToolsBlock


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
    create: CreateConfig | None = None
    apply: ApplyConfig | None = None
    delete: DeleteConfig | None = None
    patches: list[PatchConfig] = []

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
        if "create" in self.operations:
            if self.create is None:
                raise ValueError("operations includes 'create' but create config is missing")
            if self.tools.create is None:
                raise ValueError(
                    "operations includes 'create' but tools.create metadata is missing"
                )
            if "get" not in self.operations or self.get is None:
                raise ValueError(
                    "operations includes 'create' but 'get' is missing — "
                    "create reuses get's summary_copy_fields/locals/extras/link_keys "
                    "to shape the response payload. Add 'get' to operations and "
                    "provide a get config."
                )
        if "apply" in self.operations:
            if self.apply is None:
                raise ValueError("operations includes 'apply' but apply config is missing")
            if self.tools.apply is None:
                raise ValueError("operations includes 'apply' but tools.apply metadata is missing")
            if "get" not in self.operations or self.get is None:
                raise ValueError(
                    "operations includes 'apply' but 'get' is missing — "
                    "apply reuses get's response-shaping pipeline. Add 'get' "
                    "to operations and provide a get config."
                )
        if "delete" in self.operations:
            if self.delete is None:
                raise ValueError("operations includes 'delete' but delete config is missing")
            if self.tools.delete is None:
                raise ValueError(
                    "operations includes 'delete' but tools.delete metadata is missing"
                )
            if self.get is None:
                raise ValueError(
                    "operations includes 'delete' but 'get' config is missing — "
                    "delete uses get.arg_name as the resource-name argument. "
                    "Add 'get' to operations and provide a get config."
                )
        if "patch" in self.operations:
            if not self.patches:
                raise ValueError("operations includes 'patch' but patches list is empty")
            if not self.tools.patches:
                raise ValueError("operations includes 'patch' but tools.patches list is empty")
            if len(self.patches) != len(self.tools.patches):
                raise ValueError(
                    f"len(patches) ({len(self.patches)}) must equal "
                    f"len(tools.patches) ({len(self.tools.patches)}) — "
                    f"each patch entry pairs with one tools.patches entry "
                    f"by index."
                )
            if "get" not in self.operations or self.get is None:
                raise ValueError(
                    "operations includes 'patch' but 'get' is missing — "
                    "patch reuses get's response-shaping pipeline. Add 'get' "
                    "to operations and provide a get config."
                )
            verbs_seen: list[str] = []
            for index, patch in enumerate(self.patches):
                value_sources = [
                    bool(patch.args),
                    patch.target_value is not None,
                    patch.target_value_factory is not None,
                ]
                set_count = sum(value_sources)
                if set_count == 0:
                    raise ValueError(
                        f"patches[{index}] must declare exactly one of "
                        f"args, target_value, or target_value_factory — "
                        f"narrow patches need a defined subtree source."
                    )
                if set_count > 1:
                    raise ValueError(
                        f"patches[{index}] declares more than one of "
                        f"(args, target_value, target_value_factory). "
                        f"Pick exactly one: args for typed input, "
                        f"target_value for static toggles, "
                        f"target_value_factory for runtime-dynamic values."
                    )
                if patch.verb in verbs_seen:
                    raise ValueError(
                        f"patches[{index}].verb={patch.verb!r} is duplicated. "
                        f"Each patch on a descriptor must have a unique verb "
                        f"so the generated tool names don't collide."
                    )
                verbs_seen.append(patch.verb)
                expected_tool_name = f"rancher_{self.display_name_singular}_{patch.verb}"
                actual_tool_name = self.tools.patches[index].name
                if actual_tool_name != expected_tool_name:
                    raise ValueError(
                        f"tools.patches[{index}].name must be "
                        f"{expected_tool_name!r} "
                        f"(rancher_<singular>_<verb>), got "
                        f"{actual_tool_name!r}. Either update "
                        f"tools.patches[{index}].name or change "
                        f"patches[{index}].verb to keep them in sync."
                    )
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
