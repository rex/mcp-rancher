"""Pydantic descriptor schema for curated tool codegen.

A descriptor is the YAML at `catalog/curated_tools/<id>.yml`. It captures
the mechanical shape of a curated tool pack so the generator can emit
the full plumbing without per-type Python files.

Editorial pieces (output Pydantic models, normalization helpers, tool
descriptions, next-step hints) are referenced from the descriptor but
remain hand-written. The generator imports them; it does not produce
them.

The schema is split across submodules for line-limit hygiene; this
package re-exports the full public surface so
`from scripts.codegen.descriptor import Descriptor` keeps working:

- `aliases` — Literal type aliases
- `configs` — list/get read-path config models + `ArgSpec`
- `operations` — create/apply/delete/patch configs + tool metadata
- `models` — `Descriptor` / `PackDescriptor` aggregates
- `loaders` — YAML load helpers
"""

from __future__ import annotations

from .aliases import (
    AnnotationSet,
    ArgType,
    FilterPredicate,
    FilterType,
    Operation,
    Plane,
    Transport,
)
from .configs import (
    ArgSpec,
    DetailExtra,
    DetailLocal,
    FilterSpec,
    GetConfig,
    ListConfig,
    PathHelper,
)
from .loaders import (
    load_all_descriptors,
    load_all_pack_descriptors,
    load_descriptor,
    load_pack_descriptor,
)
from .models import Descriptor, PackDescriptor
from .operations import (
    ApplyConfig,
    CreateConfig,
    DeleteConfig,
    PatchConfig,
    ToolMeta,
    ToolsBlock,
)

__all__ = [
    "AnnotationSet",
    "ApplyConfig",
    "ArgSpec",
    "ArgType",
    "CreateConfig",
    "DeleteConfig",
    "Descriptor",
    "DetailExtra",
    "DetailLocal",
    "FilterPredicate",
    "FilterSpec",
    "FilterType",
    "GetConfig",
    "ListConfig",
    "Operation",
    "PackDescriptor",
    "PatchConfig",
    "PathHelper",
    "Plane",
    "ToolMeta",
    "ToolsBlock",
    "Transport",
    "load_all_descriptors",
    "load_all_pack_descriptors",
    "load_descriptor",
    "load_pack_descriptor",
]
