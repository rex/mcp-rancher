"""Publish a compact, accurate ``outputSchema`` for every tool.

WHY. `outputSchema` was **64% of this server's entire `tools/list` payload** —
353 KB of 548 KB, ~88,000 tokens charged to every client before it does any
work. Most of that is not information a model uses to decide whether to CALL a
tool; it is Pydantic's serialization scaffolding.

Four things are removed or corrected here. The first two are correctness fixes,
not optimizations:

0. **`required` promised keys the body drops.** The response envelope omits
   every null and empty value by design. The schema, derived from the model,
   still listed such properties as required whenever the model gave them no
   default — `namespace: str | None` on every namespaced list. A cluster-wide
   list therefore violated its own contract, and 32 tools failed that call for
   months. A property that can be dropped is no longer published as required;
   see `_may_be_dropped`.

1. **`suggestedNextSteps` was advertised but is never sent.** It is the internal
   backing field for the ``next_steps`` computed field. The SDK derives
   `outputSchema` from ``model_json_schema()`` in *validation* mode, where the
   backing field appears and the computed field does not — while the response
   body is the *serialization* dump, where exactly the reverse is true. So the
   published contract named a key no client can ever receive (~30 KB) and
   omitted ``nextSteps``, which every response actually carries. Both directions
   are repaired here.

2. **`title` on every field (~76 KB, 3,500 occurrences).** Pydantic generates it
   mechanically from the field name — `{"clusterId": {"title": "Cluster Id"}}`.
   The key already says it. Pure noise.

3. **`default` (~29 KB).** A default describes what to send when *input* is
   absent. On an output schema it says nothing about the response.

WHAT IS DELIBERATELY KEPT. `description` stays: it is real semantic content, and
the whole argument for this pass is that scaffolding should be cut so that
meaning survives. Nullability (`anyOf: [X, {"type": "null"}]`) also stays —
collapsing it would save ~10% while publishing a contract that says a field is
non-nullable when it can be null, which is how a strict client ends up rejecting
a valid response. That is the exact failure this repo already shipped once.

SAFETY. Every transformation either removes an annotation keyword or makes the
contract *weaker*: no `properties` key a response carries is removed, and
`required` only ever shrinks. A weaker promise cannot make a valid body
invalid. `tests/unit/test_output_contract_fleet_wide.py` holds the result to the
real thing across every tool: bodies in three shapes — full, sparse and bare —
validated against what is published here with the validator a client uses, and
every read tool called through the request path against an empty backend.

`structuredContent` is unaffected: the SDK builds it from the tool's
`fn_metadata`, which this pass does not touch. Only the *published* schema
changes.
"""

from __future__ import annotations

from typing import Any, cast

from rancher_mcp.sdk_registry import registered_tools

# Pydantic serialization scaffolding with no meaning on an output contract.
_NOISE_KEYWORDS = ("title", "default")

# The internal backing field for the `next_steps` computed field (see module
# docstring). Never present in a serialized response.
_BACKING_FIELD = "suggestedNextSteps"

# What the envelope actually emits in the backing field's place.
#
# Added at the ROOT of a schema only. `models/base.py` emits `next_steps` at the
# top level and nowhere else — nested items never set `suggested_next_steps`, so
# their computed value is empty and the envelope drops it. Declaring it on all
# ~330 nested models would therefore be both inaccurate AND more expensive than
# the field it replaces: a first cut of this pass did exactly that and gave back
# most of the saving it had just earned.
#
# Kept deliberately terse for the same reason. The model reads the real value in
# the response; the schema's job here is to be ACCURATE about the key existing,
# not to re-document it at 206 call sites.
_NEXT_STEPS_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"tool": {"type": "string"}, "args": {"type": "object"}},
    },
}


def _compact(node: object, *, at_root: bool = False) -> object:
    """Recursively strip scaffolding and repair the next-steps contract.

    ``at_root`` is true only for the schema's own top level, never inside
    ``$defs`` — see `_NEXT_STEPS_SCHEMA` for why that distinction matters.
    """

    if isinstance(node, list):
        return [_compact(item) for item in cast(list[object], node)]
    if not isinstance(node, dict):
        return node

    mapping = cast(dict[str, object], node)
    out: dict[str, object] = {}
    for key, value in mapping.items():
        if key in _NOISE_KEYWORDS:
            continue
        if key == "properties" and isinstance(value, dict):
            subschemas = cast(dict[str, object], value)
            properties: dict[str, object] = {
                name: _compact(subschema)
                for name, subschema in subschemas.items()
                if name != _BACKING_FIELD
            }
            if at_root and _BACKING_FIELD in subschemas:
                properties["nextSteps"] = dict(_NEXT_STEPS_SCHEMA)
            out[key] = properties
            continue
        if key == "required" and isinstance(value, list):
            # `required` may only name what a body always carries. Two things
            # fall short of that: the backing field removed above, and any
            # property the envelope is free to drop (see `_may_be_dropped`).
            declared = mapping.get("properties")
            subschemas = cast(dict[str, object], declared) if isinstance(declared, dict) else {}
            kept = [
                item
                for item in cast(list[object], value)
                if item != _BACKING_FIELD
                and not (isinstance(item, str) and _may_be_dropped(subschemas.get(item)))
            ]
            if kept:
                out[key] = kept
            continue
        out[key] = _compact(value)
    return out


# The only JSON types whose every value survives the response envelope.
_ALWAYS_PRESENT_TYPES = frozenset({"string", "integer", "number", "boolean"})


def _may_be_dropped(schema: object) -> bool:
    """Whether a body may legitimately arrive WITHOUT a property of this schema.

    The response envelope omits every null, every empty list and every empty
    object (`envelope.shape_envelope`, ADR-0002) — including a nested model
    that shapes down to nothing. So only a non-nullable scalar is guaranteed to
    be there: an empty string, a zero and a ``false`` are all kept.

    Errs toward "may be dropped". Wrongly calling a property optional costs a
    client nothing; wrongly calling it required fails the whole call, which is
    what 32 list tools did on every cluster-wide request.
    """

    if not isinstance(schema, dict):
        return True
    node = cast(dict[str, object], schema)
    if "$ref" in node or "allOf" in node:
        return True
    for keyword in ("anyOf", "oneOf"):
        options = node.get(keyword)
        if isinstance(options, list):
            return any(_may_be_dropped(option) for option in cast(list[object], options))
    kind = node.get("type")
    if isinstance(kind, list):
        return not set(cast(list[object], kind)) <= _ALWAYS_PRESENT_TYPES
    if kind is None:
        # Untyped: a scalar only if it is pinned to non-null literal values.
        literals = [node["const"]] if "const" in node else node.get("enum")
        return not (
            isinstance(literals, list) and literals and None not in cast(list[object], literals)
        )
    return kind not in _ALWAYS_PRESENT_TYPES


def compact_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return the compacted form of one published output schema."""

    result = _compact(schema, at_root=True)
    return cast(dict[str, Any], result) if isinstance(result, dict) else schema


def compact_input_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Strip mechanical `title` from a published INPUT schema.

    Narrower than the output pass on purpose. `default` is **kept**: on an input
    schema it states what happens when the caller omits the parameter, which is
    exactly the information that makes `cluster_id`'s default of `"local"`
    visible rather than a trap. Only `title` goes — Pydantic derives it from the
    field name (`cluster_id` → `"Cluster Id"`), so it restates the key it is
    attached to, 1,200 times over.

    Safe by construction: the SDK validates arguments through the tool's
    `fn_metadata` model, not through this published schema, and `title` is an
    annotation keyword that constrains nothing either way.
    """

    result = _strip_titles(schema)
    return cast(dict[str, Any], result) if isinstance(result, dict) else schema


def _strip_titles(node: object) -> object:
    if isinstance(node, list):
        return [_strip_titles(item) for item in cast(list[object], node)]
    if not isinstance(node, dict):
        return node
    return {
        key: _strip_titles(value)
        for key, value in cast(dict[str, object], node).items()
        if key != "title"
    }


def apply_compact_output_schemas(mcp: Any) -> None:
    """Rewrite every registered tool's published schemas in place.

    A data pass, not a wrapper: unlike the `apply_*` chain in ``server.py`` this
    mutates fields rather than the callable, so its order relative to those is
    irrelevant. Call once at construction time, never per request.
    """

    for tool in registered_tools(mcp):
        if tool.output_schema:
            tool.output_schema = compact_output_schema(tool.output_schema)
        if tool.parameters:
            tool.parameters = compact_input_schema(tool.parameters)
