"""Fleet-wide regression gate: outputSchema (validation mode) vs the REAL dump.

**The incident this gates.** FastMCP publishes each tool's ``outputSchema``
from the return model's ``model_json_schema()`` in *validation* mode, then
validates the actual response — the model's *serialization* dump — against
that published schema. A ``count`` field was given a bare
``serialization_alias="count"`` while the model field was ``cluster_count``
with no matching ``validation_alias``. The validation-mode schema therefore
required ``clusterCount``; the dumped body sent ``count``; MCP's
``jsonschema.validate()`` rejected the whole response. ``rancher_clusters_list``
returned nothing — an agent could not enumerate clusters at all. TWELVE tools
were dead this way (ADR-0002 / M-A1; see ``tests/unit/test_list_count_alias_uniform.py``,
which fixed and covers the alias-uniformity angle of this incident).

**What this file adds over that narrower test.** The existing
``test_no_serialization_alias_split_on_any_output_model`` inspects
``pydantic.fields.FieldInfo`` metadata directly across every ``RancherModel``
subclass — cheap, and it catches alias splits specifically. It cannot see:
a required field marked ``exclude=True`` (never serialized, alias or no
alias), a ``@computed_field`` edge case, or a key the base model's
``@model_serializer(mode="wrap")`` (``models/base.py::_shape_on_dump``) or
``envelope.shape_envelope`` drop outright (the ``payload`` pop, the
plumbing-key denylist). It also only checks models — not the *actual
registered tool surface*, so a model that is never wired to a tool, or a
future output shape this repo hasn't imagined yet, isn't provably covered.

This file instead:

1. Builds the server's REAL tool registry exactly as production does
   (``rancher_mcp.server.register_all_tools`` — see
   ``_output_schema_dump_parity_support.build_registered_server``), so a
   newly added tool is covered automatically the day it lands — no
   hand-maintained tool list to keep in sync.
2. For every registered tool's output model, synthesizes a maximally
   populated example straight from that model's own validation-mode
   ``outputSchema`` (the exact schema FastMCP publishes), constructs a REAL
   instance via ``model_validate``, and dumps it via
   ``model_dump(mode="json", by_alias=True)`` — the *exact* call FastMCP's
   ``func_metadata.convert_result`` makes right before handing the body to
   ``jsonschema.validate``.
3. Recursively confirms every property the schema calls REQUIRED, at every
   nesting level (root and every reachable ``$defs`` model — list-item
   models included), is actually a key in that real dump.

This is empirical, not a schema-vs-schema diff: diffing
``model_json_schema(mode="validation")`` against
``model_json_schema(mode="serialization")`` wholesale was the obvious first
approach, but every ``RancherModel`` subclass has a class-level custom
``@model_serializer`` (inherited from ``models/base.py``), and pydantic's
schema generator cannot introspect an arbitrary Python function — so for
EVERY model here, ``model_json_schema(mode="serialization")`` comes back a
bare ``{}`` (verified against ``RancherClusterList`` itself while building
this gate: ``test_serialization_mode_schema_is_blind_for_rancher_models``
below keeps that finding honest). A whole-schema diff against that blind
serialization schema would flag every required field on every model as
"missing" — useless. Running the real dump sidesteps the blindness entirely.

No live cluster, no network: every tool's dependencies (``client``,
``settings``) are irrelevant here because we never call a tool function —
we only ever construct and dump its declared return *model*.
"""

from __future__ import annotations

import pytest
from _output_schema_dump_parity_support import (
    ToolOutput,
    build_registered_server,
    check_model_dump_parity,
    iter_tool_outputs,
)
from pydantic import Field, computed_field

from rancher_mcp.models.base import RancherModel

# Built once at import time (no I/O, ~0.6s): every parametrize id below needs
# the real tool list at collection time, and pytest.mark.parametrize can only
# read data that already exists when the module is collected.
_SERVER = build_registered_server()
_TOOL_OUTPUTS: list[ToolOutput] = iter_tool_outputs(_SERVER)


def test_registry_produced_a_healthy_number_of_tool_outputs() -> None:
    """Canary against a silently-empty sweep.

    If ``register_all_tools`` broke and registered zero tools, or if every
    tool stopped publishing a structured ``outputSchema``, the parametrized
    test below would collect zero cases and vacuously "pass" — the exact
    failure mode this whole gate exists to avoid. Assert real coverage
    instead of trusting an empty list.
    """

    all_tools = _SERVER._tool_manager.list_tools()
    assert len(all_tools) > 100, (
        f"only {len(all_tools)} tools registered by register_all_tools() — "
        "expected 300+; registration may be broken"
    )
    assert len(_TOOL_OUTPUTS) == len(all_tools), (
        f"{len(all_tools) - len(_TOOL_OUTPUTS)} registered tool(s) published no "
        "structured outputSchema at all — every curated tool here returns a "
        "BaseModel and should have one; investigate before trusting this gate"
    )


@pytest.mark.parametrize(
    "tool_output",
    _TOOL_OUTPUTS,
    ids=[tool_output.tool_name for tool_output in _TOOL_OUTPUTS],
)
def test_tool_output_schema_matches_real_dump(tool_output: ToolOutput) -> None:
    """For every registered tool: outputSchema's required keys must all
    appear, at every nesting level, in the model's REAL serialized dump.

    A failure here means this tool is (or would be, given realistic data)
    the next ``rancher_clusters_list`` — MCP's ``jsonschema.validate()``
    silently rejects the entire response the moment one required key the
    schema promises never shows up in the body FastMCP actually sends.
    """

    missing = check_model_dump_parity(tool_output.model)
    assert not missing, "\n".join(
        [f"tool={tool_output.tool_name!r} model={tool_output.model.__name__!r}:"]
        + [f"  - {entry.describe(tool_output.model.__name__)}" for entry in missing]
    )


def test_serialization_mode_schema_is_blind_for_rancher_models() -> None:
    """Documents WHY this gate diffs a real dump instead of two schemas.

    Every ``RancherModel`` subclass inherits a class-level
    ``@model_serializer(mode="wrap")``. Pydantic's schema generator cannot
    introspect what an arbitrary wrap-serializer function will do to the
    dump, so ``model_json_schema(mode="serialization")`` degrades to an
    empty, useless shell for these models — it is NOT a safe source of
    truth for "what keys will the dump have". If a future pydantic upgrade
    changes this behavior, this test goes red as a loud signal to revisit
    the design note in this module's docstring and in
    ``_output_schema_dump_parity_support``.
    """

    from rancher_mcp.models.clusters_nodes import RancherClusterList

    serialization_schema = RancherClusterList.model_json_schema(mode="serialization")
    # Verified empirically while building this gate: pydantic doesn't even
    # emit an object shell for a model with an inherited whole-model
    # ``@model_serializer`` — the "serialization" schema is a bare `{}`.
    assert serialization_schema == {}


def test_gate_catches_the_motivating_bug_shape() -> None:
    """Reproduces the exact P0 and proves the gate fails loudly on it.

    Mirrors the real defect precisely: a REQUIRED field (``cluster_count``)
    given a bare ``serialization_alias="count"`` with no matching
    ``validation_alias``, on a real ``RancherModel`` subclass — so this also
    exercises the inherited wrap-serializer / envelope-shaping pipeline the
    original bug actually shipped through, not just a bare pydantic model in
    isolation. See the module docstring for the manual verification
    transcript recorded when this gate was built.
    """

    class ScratchClusterCountBug(RancherModel):
        cluster_count: int = Field(serialization_alias="count")  # BUG: no validation_alias
        clusters: list[str] = Field(default_factory=lambda: ["cluster-a"])

    missing = check_model_dump_parity(ScratchClusterCountBug)

    assert missing, (
        "gate FAILED to catch its own motivating bug: a required field with a "
        "bare serialization_alias and no validation_alias must be flagged"
    )
    assert missing[0].key == "clusterCount"
    assert "count" in missing[0].dumped_keys
    assert "clusterCount" not in missing[0].dumped_keys


def test_gate_catches_required_field_excluded_from_serialization() -> None:
    """``exclude=True`` on a REQUIRED field: never serialized, alias or no
    alias — a distinct divergence source the alias-only static check
    (``test_no_serialization_alias_split_on_any_output_model``) cannot see.
    """

    class ScratchExcludeBug(RancherModel):
        secret_val: str = Field(exclude=True)

    missing = check_model_dump_parity(ScratchExcludeBug)

    assert missing, "gate failed to catch a required exclude=True field"
    assert missing[0].key == "secretVal"


def test_gate_catches_required_field_dropped_by_envelope_plumbing_denylist() -> None:
    """A required field whose alias collides with ``envelope._DROP_KEYS``
    (``uid``, ``links``, ``generation``, ...) is unconditionally stripped by
    ``shape_envelope`` regardless of value — this gate must catch that too,
    not just alias splits.
    """

    class ScratchPlumbingCollisionBug(RancherModel):
        uid: str  # required; to_camel("uid") == "uid" == a _DROP_KEYS entry

    missing = check_model_dump_parity(ScratchPlumbingCollisionBug)

    assert missing, "gate failed to catch a required field shadowed by envelope's plumbing denylist"
    assert missing[0].key == "uid"


def test_gate_catches_alias_split_on_nested_list_item_model() -> None:
    """The same alias-split bug one level down, inside a list's item model —
    proves the recursion into nested ``$defs`` actually runs, not just the
    root model (nested list-item models carry the same exposure per the
    task brief).
    """

    class ScratchNestedItem(RancherModel):
        item_id: str = Field(serialization_alias="id")  # BUG shape, nested

    class ScratchNestedList(RancherModel):
        items: list[ScratchNestedItem] = Field(default_factory=list)
        total: int = 1

    missing = check_model_dump_parity(ScratchNestedList)

    assert missing, "gate failed to catch an alias split on a nested list-item model"
    assert missing[0].path == "ScratchNestedList.items[0]"
    assert missing[0].key == "itemId"


def test_gate_does_not_flag_aligned_validation_and_serialization_alias() -> None:
    """Negative control: the actual M-A1 FIX shape (``validation_alias`` and
    ``serialization_alias`` both set to the same key) must report clean —
    a gate that cries wolf on the correct pattern is as useless as one that
    misses the bug.
    """

    class ScratchGoodShape(RancherModel):
        cluster_count: int = Field(validation_alias="count", serialization_alias="count")
        clusters: list[str] = Field(default_factory=lambda: ["cluster-a"])

    assert check_model_dump_parity(ScratchGoodShape) == ()


def test_gate_does_not_flag_computed_fields() -> None:
    """Negative control: a ``@computed_field`` is additive-only (never part
    of the validation-mode schema's ``required`` list, since it is never an
    input) and must never be reported as a missing key.
    """

    class ScratchComputedOnly(RancherModel):
        name: str = "x"

        @computed_field  # type: ignore[prop-decorator]
        @property
        def upper_name(self) -> str:
            return self.name.upper()

    assert check_model_dump_parity(ScratchComputedOnly) == ()
