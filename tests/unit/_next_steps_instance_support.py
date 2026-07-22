"""Builds a representative model instance for one ``NextStepDeclaration``
(see ``_next_steps_registry_support.py``), so the gate can read the REAL,
computed ``next_steps`` output for a real production declaration.

Split out of ``_next_steps_registry_support.py`` purely to keep each file
under the architecture line-limit gate (`tool_module_rule` — one concern per
module); the two are a matched pair used together by
``test_next_steps_registry_gate.py``.
"""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING, Any

from _output_schema_dump_parity_support import synthesize_example
from pydantic import BaseModel

if TYPE_CHECKING:
    from _next_steps_registry_support import NextStepDeclaration


@cache
def _base_instance(model: type[BaseModel]) -> BaseModel:
    """A maximally-populated instance of *model*, memoized per class.

    Reuses ``_output_schema_dump_parity_support.synthesize_example`` — the
    schema/dump-parity gate's own "how do I build a valid instance of an
    arbitrary RancherModel subclass" solution — rather than reinventing it.
    Every field, required AND optional, gets a concrete, non-empty value, so
    a model that CAN carry ``cluster_id``/``namespace`` always does here.
    """

    schema = model.model_json_schema(mode="validation")
    defs = schema.get("$defs", {})
    example = synthesize_example(schema, defs)
    return model.model_validate(example)


def build_representative_instance(declaration: NextStepDeclaration) -> BaseModel:
    """A maximally-populated instance of *declaration*'s model, with
    ``suggested_next_steps`` overridden to the declaration's REAL target
    list — replacing whatever placeholder the schema-driven synthesis put
    there (it fills every field including that one, generically)."""

    base = _base_instance(declaration.model)
    return base.model_copy(update={"suggested_next_steps": list(declaration.target_names)})


def build_representative_next_steps(declaration: NextStepDeclaration) -> list[dict[str, Any]]:
    """The REAL, computed ``next_steps`` output for *declaration*.

    Plain property access — no need to go through ``model_dump``/envelope
    shaping, since ``tool``/``args`` are bare dict keys a computed field
    returns, never touched by alias generation or the redaction/plumbing
    scrub.
    """

    return build_representative_instance(declaration).next_steps  # type: ignore[no-any-return]
