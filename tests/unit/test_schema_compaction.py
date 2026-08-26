"""The compaction pass rewrites the published contract for all 206 tools.

That makes it the highest-risk code in the repo by blast radius: a mistake here
reproduces the class of defect that once made every list tool return nothing.
These tests pin both what it removes and — more importantly — what it must never
touch.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from rancher_mcp.schema_compaction import (
    apply_compact_output_schemas,
    compact_input_schema,
    compact_output_schema,
)
from rancher_mcp.sdk_registry import registered_tools
from rancher_mcp.server import register_all_tools


def _sample_output_schema() -> dict[str, Any]:
    """Shaped like what Pydantic actually emits for a RancherModel list."""

    return {
        "type": "object",
        "title": "RancherClusterList",
        "description": "Cluster inventory.",
        "properties": {
            "count": {"type": "integer", "title": "Count"},
            "clusters": {
                "type": "array",
                "title": "Clusters",
                "items": {"$ref": "#/$defs/RancherClusterSummary"},
            },
            "namespace": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "title": "Namespace",
                "default": None,
            },
            "suggestedNextSteps": {
                "type": "array",
                "title": "Suggested Next Steps",
                "items": {"type": "string"},
                "default": [],
            },
        },
        "required": ["count", "clusters"],
        "$defs": {
            "RancherClusterSummary": {
                "type": "object",
                "title": "RancherClusterSummary",
                "description": "One cluster.",
                "properties": {
                    "id": {"type": "string", "title": "Id"},
                    "suggestedNextSteps": {"type": "array", "title": "S", "default": []},
                },
                "required": ["id"],
            }
        },
    }


def test_mechanical_scaffolding_is_removed() -> None:
    out = compact_output_schema(_sample_output_schema())
    assert "title" not in out
    assert "title" not in out["properties"]["count"]
    assert "default" not in out["properties"]["namespace"]
    assert "title" not in out["$defs"]["RancherClusterSummary"]["properties"]["id"]


def test_descriptions_are_preserved() -> None:
    """The entire argument for this pass is that scaffolding goes so that
    MEANING survives. Stripping descriptions too would invert it."""

    out = compact_output_schema(_sample_output_schema())
    assert out["description"] == "Cluster inventory."
    assert out["$defs"]["RancherClusterSummary"]["description"] == "One cluster."


def test_nullability_is_preserved() -> None:
    """Collapsing `anyOf: [X, null]` would save ~10% and publish a contract
    claiming a field is non-nullable when it can be null — which is how a
    strict client rejects a perfectly valid response."""

    out = compact_output_schema(_sample_output_schema())
    assert out["properties"]["namespace"]["anyOf"] == [{"type": "string"}, {"type": "null"}]


def test_backing_field_is_replaced_by_what_is_actually_sent() -> None:
    """`suggestedNextSteps` is the validation-mode backing field and never
    appears in a response; `nextSteps` is the computed field that always does.
    The published schema had it exactly backwards."""

    out = compact_output_schema(_sample_output_schema())
    root = out["properties"]
    assert "suggestedNextSteps" not in root
    assert "nextSteps" in root
    assert root["nextSteps"]["type"] == "array"


def test_next_steps_is_added_at_the_root_only() -> None:
    """Nested items never set `suggested_next_steps`, so their computed value is
    empty and the envelope drops it. Declaring it on every nested model would be
    inaccurate AND cost more than the field it replaces — a first cut of this
    pass did that and gave back most of its own saving."""

    out = compact_output_schema(_sample_output_schema())
    nested = out["$defs"]["RancherClusterSummary"]["properties"]
    assert "suggestedNextSteps" not in nested
    assert "nextSteps" not in nested


def test_required_never_references_a_removed_property() -> None:
    """The invariant that matters. A `required` entry naming a key the body
    never sends is precisely the schema/body split of the clusterCount P0."""

    schema = _sample_output_schema()
    schema["required"] = ["count", "suggestedNextSteps"]
    out = compact_output_schema(schema)
    assert out["required"] == ["count"]
    for key in out.get("required", []):
        assert key in out["properties"], f"required key {key!r} has no property"


def test_input_schema_keeps_defaults_but_drops_titles() -> None:
    """Asymmetric on purpose: a default on an INPUT says what happens when the
    caller omits it — that is what makes `cluster_id="local"` visible instead of
    a trap. On an output it says nothing."""

    compacted = compact_input_schema(
        {
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string", "title": "Cluster Id", "default": "local"},
            },
        }
    )
    assert compacted["properties"]["cluster_id"]["default"] == "local"
    assert "title" not in compacted["properties"]["cluster_id"]


def test_compaction_is_idempotent() -> None:
    once = compact_output_schema(_sample_output_schema())
    assert compact_output_schema(once) == once


def test_every_registered_tool_survives_compaction_with_a_coherent_schema() -> None:
    """Fleet-wide backstop over the real registry: after the pass, no tool may
    require a key it does not also declare."""

    mcp = FastMCP(name="compaction-probe")
    register_all_tools(mcp)
    apply_compact_output_schemas(mcp)

    offenders: list[str] = []
    for tool in registered_tools(mcp):
        for schema, label in ((tool.output_schema, "output"), (tool.parameters, "input")):
            if not schema:
                continue
            declared = set(schema.get("properties", {}))
            for key in schema.get("required", []):
                if key not in declared:
                    offenders.append(f"{tool.name} {label}: requires undeclared {key!r}")
    assert not offenders, offenders
