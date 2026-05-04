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
Operation = Literal["list", "get", "create", "apply", "patch", "delete"]
AnnotationSet = Literal[
    "READ_ONLY",
    "SAFE_WRITE",
    "IDEMPOTENT_WRITE",
    "DESTRUCTIVE",
    "UNKNOWN_ACTION",
]


class FilterSpec(BaseModel):
    """A post-fetch client-side filter on the list response."""

    model_config = ConfigDict(extra="forbid")

    name: str
    """Tool argument name (also the local variable name)."""

    summary_field: str
    """Attribute on the summary model to compare against."""


class ListConfig(BaseModel):
    """List operation configuration."""

    model_config = ConfigDict(extra="forbid")

    query_params: list[Literal["limit", "label_selector", "field_selector", "continue_token"]]
    """Steve query-builder kwargs to pass through."""

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

    namespaced: bool = True
    """Whether the resource is namespaced. Affects path templating."""

    list_path: str
    """List path template (e.g. `/pods/{namespace}` or `/storageclasses`)."""

    detail_path: str
    """Detail path template (e.g. `/pods/{namespace}/{pod_name}`)."""

    # --- Models (full import paths) --------------------------------

    list_response_model: str
    """Full import path to list response model class."""

    detail_response_model: str
    """Full import path to detail response model class."""

    # --- Shared imports from tools/<pack>/shared.py ----------------

    shared_imports: list[str] = []
    """Names imported from `tools.<pack>.shared` (e.g. `data_items`)."""

    summary_function: str
    """Name of the summary normalizer function (e.g. `pod_summary_from_payload`)."""

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
        if self.namespaced and "{namespace}" not in self.list_path:
            raise ValueError("namespaced=true requires {namespace} in list_path")
        if self.namespaced and "{namespace}" not in self.detail_path:
            raise ValueError("namespaced=true requires {namespace} in detail_path")
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
