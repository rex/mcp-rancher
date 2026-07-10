"""Build emission plans from descriptors.

A plan is a per-pack data structure ready for Jinja rendering. It holds:

- the resolved descriptor list for that pack
- per-descriptor template context (paths, model class names, helper
  functions injected as Jinja globals like `qp_type`)
- pack-level register block (sorted import groups, register entries,
  the union of annotation imports needed)

Keeping this between descriptor.py and emitter.py prevents the templates
from doing complex computation in Jinja and prevents the descriptor
schema from carrying derived fields.

Split across submodules for line-limit hygiene; this package re-exports
the full public surface so `from scripts.codegen.plan import ...` keeps
working:

- `helpers` — query-param / arg-type lookup tables + accessors
- `module` — per-descriptor `ModuleContext` + builder
- `pack` — per-pack `PackContext`, register entries + builder
"""

from __future__ import annotations

from .helpers import (
    ARG_TYPES_PYTHON,
    QP_KWARGS,
    QP_TYPES,
    arg_python_type,
    qp_kwarg,
    qp_type,
    split_model_path,
)
from .module import ModuleContext, build_module_context
from .pack import (
    ImportEntry,
    PackContext,
    RegistrationEntry,
    build_pack_contexts,
)

__all__ = [
    "ARG_TYPES_PYTHON",
    "QP_KWARGS",
    "QP_TYPES",
    "ImportEntry",
    "ModuleContext",
    "PackContext",
    "RegistrationEntry",
    "arg_python_type",
    "build_module_context",
    "build_pack_contexts",
    "qp_kwarg",
    "qp_type",
    "split_model_path",
]
