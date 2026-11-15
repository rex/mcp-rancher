"""Build real response bodies in several shapes and judge them the way a client does.

The older parity gate (``_output_schema_dump_parity_support``) asks one question
of one shape: given a *maximally populated* instance, does the dump carry every
key the model's schema calls required? It was written after a required key was
renamed out from under its schema, and it catches that.

It cannot catch the opposite failure, which is the one that shipped: a key that
is required by the schema and **dropped because it was empty**. The response
envelope omits every null, empty list and empty object by design (ADR-0002), so
a cluster-wide list — ``namespace`` omitted — came back with no ``namespace``
key while its schema still demanded one. In a maximally populated example
nothing is ever empty, so that gate could not see it.

This module fills in the other shapes and changes the judge:

* **full** — everything populated (the old shape);
* **sparse** — every property present, every list holding one item, every leaf
  as empty as its type allows. Exercises nested and item models with nothing in
  them;
* **bare** — only what the model cannot be constructed without, and that as
  empty as allowed. The "nothing found, nothing set" response.

Each is built through the real model (``model_validate`` then the same
``model_dump`` the SDK calls) and validated with ``jsonschema`` against the
schema the tool actually **publishes** — the one a client is handed — not the
model's own schema, which the publishing pass rewrites.
"""

from __future__ import annotations

from typing import Any, Literal

from _output_schema_dump_parity_support import (
    _branch_type,  # pyright: ignore[reportPrivateUsage]
    _implied_type,  # pyright: ignore[reportPrivateUsage]
    _resolve_ref,  # pyright: ignore[reportPrivateUsage]
    synthesize_example,
)
from jsonschema import Draft202012Validator
from pydantic import BaseModel

Shape = Literal["full", "sparse", "bare"]
SHAPES: tuple[Shape, ...] = ("full", "sparse", "bare")

_STRING_FILL = "example-value"


def _emptiest(
    node: dict[str, Any],
    defs: dict[str, Any],
    *,
    keep_structure: bool,
    _resolving: frozenset[str] = frozenset(),
    _depth: int = 0,
) -> Any:
    """The emptiest JSON value schema fragment *node* accepts.

    With ``keep_structure`` every object property is present, every array holds
    one item and a nullable nested model is instantiated rather than left null
    — so the emptiness reaches the leaves of nested models instead of stopping
    at the first optional container. Without it, only required properties
    appear, arrays are empty and anything nullable is null.
    """

    if _depth > 40:  # pragma: no cover - guards a pathological self-reference
        return None

    ref_name, node = _resolve_ref(node, defs)
    if ref_name is not None:
        if ref_name in _resolving:
            return None
        _resolving = _resolving | {ref_name}

    def recurse(sub: dict[str, Any]) -> Any:
        return _emptiest(
            sub, defs, keep_structure=keep_structure, _resolving=_resolving, _depth=_depth + 1
        )

    branches: list[dict[str, Any]] = node.get("anyOf") or node.get("oneOf") or []
    if branches:
        non_null = [branch for branch in branches if _branch_type(branch, defs) != "null"]
        nullable = len(non_null) < len(branches)
        container = bool(non_null) and _branch_type(non_null[0], defs) in ("object", "array")
        if nullable and not (keep_structure and container):
            return None
        return recurse(non_null[0] if non_null else branches[0])

    if "allOf" in node:
        merged: dict[str, Any] = {}
        for part in node["allOf"]:
            merged.update(_resolve_ref(part, defs)[1])
        return recurse(merged)

    if "const" in node:
        return node["const"]
    if node.get("enum"):
        return node["enum"][0]

    kind = _implied_type(node)
    if kind == "string":
        return _STRING_FILL
    if kind == "boolean":
        return False
    if kind in ("integer", "number"):
        floor = node.get("minimum", 0)
        exclusive = node.get("exclusiveMinimum")
        value = max(0, int(floor)) if isinstance(floor, int | float) else 0
        if isinstance(exclusive, int | float):
            value = max(value, int(exclusive) + 1)
        return value if kind == "integer" else float(value)
    if kind == "array":
        items = node.get("items")
        if keep_structure and isinstance(items, dict):
            return [recurse(items)]
        return []
    if kind == "object":
        properties = node.get("properties")
        if isinstance(properties, dict) and properties:
            required = set(node.get("required", []))
            return {
                key: recurse(sub)
                for key, sub in properties.items()
                if keep_structure or key in required
            }
        additional = node.get("additionalProperties")
        if keep_structure and isinstance(additional, dict):
            return {"exampleKey": recurse(additional)}
        return {}
    return None  # null, or an untyped leaf: nothing is the emptiest thing it can be


def build_body(model: type[BaseModel], shape: Shape) -> dict[str, Any]:
    """A real response body of *model* in the given shape.

    Constructed from the model's own validation-mode schema, passed through
    ``model_validate`` and dumped exactly as the SDK dumps a tool's return
    value — so it has been through every serializer the real thing goes through.
    """

    schema = model.model_json_schema(mode="validation")
    defs = schema.get("$defs", {})
    if shape == "full":
        example = synthesize_example(schema, defs)
    else:
        example = _emptiest(schema, defs, keep_structure=shape == "sparse")
    return model.model_validate(example).model_dump(mode="json", by_alias=True)


def violations(published_schema: dict[str, Any], body: dict[str, Any]) -> list[str]:
    """Every way *body* fails the schema a client was given, most telling first."""

    validator = Draft202012Validator(published_schema)
    found = sorted(validator.iter_errors(body), key=lambda error: list(error.absolute_path))
    return [
        f"at {'/'.join(str(part) for part in error.absolute_path) or '(root)'}: {error.message}"
        for error in found
    ]
