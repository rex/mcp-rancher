"""Shared support for the FastMCP output-schema / actual-dump parity gate.

FastMCP publishes each tool's ``outputSchema`` from
``model.model_json_schema()`` in **validation** mode — the default, unchanged
by FastMCP (see ``func_metadata._try_create_model_and_schema``) — then
validates the ACTUAL response body against that schema (see
``mcp.server.lowlevel.server.Server.call_tool``'s
``jsonschema.validate(instance=maybe_structured_content, schema=tool.outputSchema)``).
That body is ``output_model.model_validate(result).model_dump(mode="json",
by_alias=True)`` (``FuncMetadata.convert_result``) — the model's own real
dump, which for every ``RancherModel`` subclass runs through the inherited
``@model_serializer(mode="wrap")`` (``models/base.py::_shape_on_dump``) and
the ``envelope.shape_envelope`` pass it calls.

Any divergence between what the VALIDATION-mode schema calls REQUIRED and
what that real dump can ever produce makes ``jsonschema.validate`` reject the
ENTIRE tool response. This is exactly the ``clusterCount`` P0 (ADR-0002 /
M-A1): a bare ``serialization_alias="count"`` with no matching
``validation_alias`` made the schema require ``clusterCount`` while the dump
emitted ``count``, and twelve list tools went silently dark.

This module does NOT diff ``model_json_schema(mode="validation")`` against
``model_json_schema(mode="serialization")`` wholesale — the obvious first
approach — because every ``RancherModel`` subclass inherits a class-level
custom ``@model_serializer``, which pydantic's schema generator cannot
introspect: ``model_json_schema(mode="serialization")`` comes back a bare
``{}`` for every model here (verified against ``RancherClusterList``; see
``test_serialization_mode_schema_is_blind_for_rancher_models``). A diff
against that blind schema would flag every required field on every model as
"missing" — useless. Instead this module builds a REAL instance from the
schema (:func:`synthesize_example`), runs it through the REAL
``model_validate`` + ``model_dump(mode="json", by_alias=True)`` FastMCP
itself calls, and diffs the schema's ``required`` lists against the keys
that dump *actually* produced — recursively, through every nested ``$defs``
model reachable from the root.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

# A concrete, non-empty filler for every JSON-schema leaf type. Never `None`
# and never empty: `envelope.shape_envelope` (every `RancherModel`'s dump runs
# through it) drops any key whose value is empty, so an under-populated
# example would make fields disappear for the WRONG reason (incidental
# emptiness) instead of the reason this gate exists to catch (a structural
# alias/exclude/wrap-serializer divergence).
_STRING_FILL = "example-value"


@dataclass(frozen=True, slots=True)
class ToolOutput:
    """One registered tool's name and its structured-output model class."""

    tool_name: str
    model: type[BaseModel]


def build_registered_server() -> FastMCP:
    """Construct a FastMCP server with every production tool registered.

    Mirrors ``rancher_mcp.server.create_mcp_server`` minus the
    settings-dependent name/instructions, so this needs no
    ``RANCHER_URL`` / ``RANCHER_TOKEN`` / ``.env`` and cannot flake on
    missing credentials or a live cluster.
    """

    from rancher_mcp.server import register_all_tools

    mcp = FastMCP(name="schema-dump-parity-probe", instructions="probe")
    register_all_tools(mcp)
    return mcp


def iter_tool_outputs(mcp: FastMCP) -> list[ToolOutput]:
    """Every registered tool that publishes a structured ``outputSchema``.

    Reads FastMCP's own internal tool registry (``_tool_manager``) rather
    than a hand-maintained list, so a newly registered tool is covered
    automatically. The ``apply_*`` post-processing passes in
    ``register_all_tools`` only ever rewrap ``Tool.fn`` — never
    ``Tool.fn_metadata`` — so ``fn_metadata.output_model`` is always the
    real, production-accurate model FastMCP derived the schema from.
    """

    outputs: list[ToolOutput] = []
    for tool in mcp._tool_manager.list_tools():
        model = tool.fn_metadata.output_model
        if model is not None and tool.output_schema is not None:
            outputs.append(ToolOutput(tool_name=tool.name, model=model))
    return outputs


def _resolve_ref(node: dict[str, Any], defs: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """Follow one ``$ref`` into *defs*; pass non-``$ref`` nodes through."""

    ref = node.get("$ref")
    if isinstance(ref, str):
        name = ref.rsplit("/", 1)[-1]
        return name, defs.get(name, {})
    return None, node


def _implied_type(node: dict[str, Any]) -> str | None:
    """*node*'s JSON-schema type, inferring "object"/"array" when pydantic
    omits an explicit ``type`` key (e.g. ``additionalProperties``-only dicts)."""

    node_type = node.get("type")
    if isinstance(node_type, str):
        return node_type
    if "properties" in node or "additionalProperties" in node:
        return "object"
    if "items" in node:
        return "array"
    return None


def _branch_type(branch: dict[str, Any], defs: dict[str, Any]) -> str | None:
    """The effective type of one ``anyOf``/``oneOf`` branch (``$ref``-resolved
    first, so ``Optional[SomeModel]`` reads as an ``object`` branch)."""

    _, resolved = _resolve_ref(branch, defs)
    return _implied_type(resolved)


def _pick_any_of_branch(branches: list[dict[str, Any]], defs: dict[str, Any]) -> dict[str, Any]:
    """Prefer the first non-null ``anyOf``/``oneOf`` branch.

    Mirrors ``Optional[X]``'s ``anyOf: [X, {"type": "null"}]`` shape: always
    synthesizing the real ``X`` branch (never bare ``None``) keeps optional
    fields concretely populated, so envelope emptiness-dropping never
    masquerades as a structural divergence.
    """

    non_null = [branch for branch in branches if _branch_type(branch, defs) != "null"]
    return non_null[0] if non_null else branches[0]


def synthesize_example(
    node: dict[str, Any],
    defs: dict[str, Any],
    *,
    _resolving: frozenset[str] = frozenset(),
    _depth: int = 0,
) -> Any:
    """Build a maximally-populated JSON value matching validation-mode schema
    fragment *node*.

    Every property at every level — required AND optional — gets a concrete,
    non-empty value, so the only way the real dump can end up missing a
    REQUIRED key is a genuine structural divergence, never mere emptiness.
    """

    if _depth > 40:  # pragma: no cover - guards a pathological self-reference
        return None

    ref_name, node = _resolve_ref(node, defs)
    if ref_name is not None:
        if ref_name in _resolving:
            return None  # break a self-referential $ref cycle
        _resolving = _resolving | {ref_name}

    if "anyOf" in node or "oneOf" in node:
        branches = node.get("anyOf") or node.get("oneOf") or []
        chosen = _pick_any_of_branch(branches, defs)
        return synthesize_example(chosen, defs, _resolving=_resolving, _depth=_depth + 1)

    if "allOf" in node:
        merged: dict[str, Any] = {}
        for part in node["allOf"]:
            _, resolved_part = _resolve_ref(part, defs)
            merged.update(resolved_part)
        return synthesize_example(merged, defs, _resolving=_resolving, _depth=_depth + 1)

    if "const" in node:
        return node["const"]
    if node.get("enum"):
        return node["enum"][0]

    node_type = _implied_type(node)

    if node_type == "null":
        return None
    if node_type == "string":
        return _STRING_FILL
    if node_type == "boolean":
        return True
    if node_type == "integer":
        minimum = node.get("minimum")
        exclusive_minimum = node.get("exclusiveMinimum")
        value = 1
        if isinstance(minimum, int | float):
            value = max(value, int(minimum))
        if isinstance(exclusive_minimum, int | float):
            value = max(value, int(exclusive_minimum) + 1)
        return value
    if node_type == "number":
        return 1.0
    if node_type == "array":
        item_schema = node.get("items")
        if not isinstance(item_schema, dict):
            return [_STRING_FILL]
        return [synthesize_example(item_schema, defs, _resolving=_resolving, _depth=_depth + 1)]
    if node_type == "object":
        props = node.get("properties")
        if isinstance(props, dict) and props:
            return {
                key: synthesize_example(sub, defs, _resolving=_resolving, _depth=_depth + 1)
                for key, sub in props.items()
            }
        additional = node.get("additionalProperties")
        if isinstance(additional, dict):
            return {
                "exampleKey": synthesize_example(
                    additional, defs, _resolving=_resolving, _depth=_depth + 1
                )
            }
        if additional is False:
            return {}
        return {"exampleKey": _STRING_FILL}

    # Untyped leaf (bare `Any`): still concrete and non-empty.
    return _STRING_FILL


def _json_kind(value: Any) -> str | None:
    """The JSON-schema type name Python *value* corresponds to."""

    if value is None:
        return "null"
    if isinstance(value, bool):  # must precede the int check: bool is an int
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return None


@dataclass(frozen=True, slots=True)
class MissingRequiredKey:
    """One REQUIRED schema property the real dump never produced."""

    path: str
    key: str
    dumped_keys: tuple[str, ...]

    def describe(self, model_name: str) -> str:
        """Actionable failure text: model, path, offending key, both sides."""

        return (
            f"model={model_name} path={self.path!r} key={self.key!r}: the outputSchema "
            f"FastMCP publishes (model_json_schema(mode='validation')) REQUIRES "
            f"{self.key!r} at this path, but the REAL dump (model_validate(...)"
            f".model_dump(mode='json', by_alias=True) — exactly what FastMCP validates "
            f"the response against) never produces it. Keys the dump actually has at "
            f"this path: {sorted(self.dumped_keys)!r}. This is the schema-vs-body split "
            f"that silently killed rancher_clusters_list and 11 other list tools (the "
            f"clusterCount P0): MCP's jsonschema.validate() rejects the WHOLE response "
            f"when a required key is missing, so the tool returns nothing to the client "
            f"even though the server did the work correctly."
        )


def find_missing_required_keys(
    node: dict[str, Any],
    defs: dict[str, Any],
    data: Any,
    path: str,
) -> list[MissingRequiredKey]:
    """Recursively diff *node*'s (validation-mode) ``required`` lists against
    the keys *data* (the model's REAL dump) actually has, at every nesting
    level the schema and the dump both reach.
    """

    _, node = _resolve_ref(node, defs)

    if "anyOf" in node or "oneOf" in node:
        branches = node.get("anyOf") or node.get("oneOf") or []
        kind = _json_kind(data)
        matching = [branch for branch in branches if _branch_type(branch, defs) == kind]
        if not matching:
            if data is None:
                return []  # a legitimately-absent optional branch
            matching = [branch for branch in branches if _branch_type(branch, defs) != "null"]
        if not matching:
            return []
        return find_missing_required_keys(matching[0], defs, data, path)

    if "allOf" in node:
        merged: dict[str, Any] = {}
        for part in node["allOf"]:
            _, resolved_part = _resolve_ref(part, defs)
            merged.update(resolved_part)
        return find_missing_required_keys(merged, defs, data, path)

    node_type = _implied_type(node)
    errors: list[MissingRequiredKey] = []

    if node_type == "object":
        if not isinstance(data, dict):
            return errors
        required = node.get("required", [])
        actual_keys = tuple(data.keys())
        for key in required:
            if key not in data:
                errors.append(MissingRequiredKey(path=path, key=key, dumped_keys=actual_keys))
        props = node.get("properties")
        if isinstance(props, dict):
            for key, sub_schema in props.items():
                if key in data and data[key] is not None:
                    errors.extend(
                        find_missing_required_keys(sub_schema, defs, data[key], f"{path}.{key}")
                    )
        additional = node.get("additionalProperties")
        if isinstance(additional, dict):
            for key, value in data.items():
                if isinstance(props, dict) and key in props:
                    continue
                errors.extend(find_missing_required_keys(additional, defs, value, f"{path}.{key}"))
        return errors

    if node_type == "array":
        if not isinstance(data, list):
            return errors
        item_schema = node.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(data):
                errors.extend(
                    find_missing_required_keys(item_schema, defs, item, f"{path}[{index}]")
                )
        return errors

    return errors  # scalar leaf: nothing further to check


@cache
def check_model_dump_parity(model: type[BaseModel]) -> tuple[MissingRequiredKey, ...]:
    """The core empirical assertion for one output model, memoized per class.

    Builds a maximally-populated synthetic instance from the model's OWN
    validation-mode ``outputSchema``, validates it (``model_validate``), and
    dumps it exactly as FastMCP's ``func_metadata.convert_result`` does
    (``model_dump(mode="json", by_alias=True)``) before handing the body to
    ``jsonschema.validate``. Then recursively confirms every property the
    schema calls REQUIRED, at every nesting level, is a key in that real dump.

    Memoized because ~321 registered tools share only ~177 distinct output
    models: callers should parametrize per-tool for an actionable failure
    message, relying on this cache for the work to run once per model class.
    """

    schema = model.model_json_schema(mode="validation")
    defs = schema.get("$defs", {})
    example = synthesize_example(schema, defs)
    instance = model.model_validate(example)
    dumped = instance.model_dump(mode="json", by_alias=True)
    return tuple(find_missing_required_keys(schema, defs, dumped, model.__name__))
