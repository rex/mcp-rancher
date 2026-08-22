"""Exhaustive sweep over the GENERATED kind registry itself
(`tools/resource_kinds/_generated_kinds.py`), covering every one of the 42
kinds' `detail_path` callables — not just the handful of representative
kinds `test_resource_kinds_metadata_tools.py` / `test_resource_kinds_delete_
tools.py` exercise end-to-end through the hand-written dispatch tools.

`detail_path` is a pure function (no I/O), so this needs no client stub —
it directly proves every one of the 42 (or 34, for delete) code-generated
path-building functions produces a plausible, non-empty path and correctly
enforces the namespace-required guard, without needing per-kind hand-picked
test cases. This is the fleet-wide complement to the representative,
behavior-level tests in the two files above.
"""

from __future__ import annotations

import pytest

from rancher_mcp.tools.resource_kinds._generated_kinds import (
    ANNOTATABLE_RESOURCE_KINDS,
    DELETABLE_RESOURCE_KINDS,
    LABELABLE_RESOURCE_KINDS,
    RESOURCE_KIND_REGISTRY,
)


def test_registry_has_the_expected_kind_counts() -> None:
    """Locks in the F2 collapse's exact shape: 42 labelable/annotatable
    kinds, 34 deletable — matching the 42 set_labels + 42 set_annotations +
    34 delete tools that were retired."""

    assert len(RESOURCE_KIND_REGISTRY) == 42
    assert len(LABELABLE_RESOURCE_KINDS) == 42
    assert len(ANNOTATABLE_RESOURCE_KINDS) == 42
    assert len(DELETABLE_RESOURCE_KINDS) == 34


def test_labelable_annotatable_deletable_tuples_match_the_registry_flags() -> None:
    """The three closed-enum tuples are derived from the SAME registry the
    dispatch tools use — this catches a codegen bug where the enum and the
    routing table quietly disagree."""

    labelable = {kind for kind, spec in RESOURCE_KIND_REGISTRY.items() if spec.supports_labels}
    annotatable = {
        kind for kind, spec in RESOURCE_KIND_REGISTRY.items() if spec.supports_annotations
    }
    deletable = {kind for kind, spec in RESOURCE_KIND_REGISTRY.items() if spec.supports_delete}

    assert set(LABELABLE_RESOURCE_KINDS) == labelable
    assert set(ANNOTATABLE_RESOURCE_KINDS) == annotatable
    assert set(DELETABLE_RESOURCE_KINDS) == deletable


def test_every_kind_key_matches_its_own_spec_kind_field() -> None:
    for key, spec in RESOURCE_KIND_REGISTRY.items():
        assert key == spec.kind


@pytest.mark.parametrize("kind", sorted(RESOURCE_KIND_REGISTRY))
def test_detail_path_builds_a_plausible_path_for_every_kind(kind: str) -> None:
    """Every one of the 42 generated `detail_path` callables must return a
    non-empty string containing the resource name, using EITHER the
    namespaced call shape (namespace supplied) or the cluster-scoped shape
    (namespace=None) depending on the kind's own `namespaced` flag."""

    spec = RESOURCE_KIND_REGISTRY[kind]
    namespace = "test-namespace" if spec.namespaced else None

    path = spec.detail_path("c-test", namespace, "my-resource")

    assert isinstance(path, str)
    assert path
    assert "my-resource" in path
    if spec.namespaced:
        assert "test-namespace" in path


@pytest.mark.parametrize(
    "kind", sorted(kind for kind, spec in RESOURCE_KIND_REGISTRY.items() if spec.namespaced)
)
def test_detail_path_raises_when_namespace_missing_for_namespaced_kind(kind: str) -> None:
    """The generated per-kind guard (`if namespace is None: raise
    ValueError(...)`) fires for every namespaced kind — the defensive
    backstop behind `tools/resource_kinds/shared.py::resolve_namespace`."""

    spec = RESOURCE_KIND_REGISTRY[kind]

    with pytest.raises(ValueError, match="namespace"):
        spec.detail_path("c-test", None, "my-resource")


@pytest.mark.parametrize(
    "kind", sorted(kind for kind, spec in RESOURCE_KIND_REGISTRY.items() if not spec.namespaced)
)
def test_detail_path_ignores_namespace_for_cluster_scoped_kind(kind: str) -> None:
    """A cluster-scoped kind's path must be IDENTICAL whether or not a
    (spurious) namespace is passed — it is a uniform-signature dispatch
    detail, never a real scope for these kinds."""

    spec = RESOURCE_KIND_REGISTRY[kind]

    without = spec.detail_path("c-test", None, "my-resource")
    with_spurious = spec.detail_path("c-test", "should-be-ignored", "my-resource")

    assert without == with_spurious
    assert "should-be-ignored" not in without


def test_get_and_list_tools_are_real_registered_tools_for_every_kind() -> None:
    """Cheap, no-server-needed cross-check that every `get_tool`/`list_tool`
    name looks like a real tool name (the full "is it actually registered"
    proof lives in the next_steps registry gate, which builds the real
    server; this just guards the generated registry's own internal
    consistency)."""

    for spec in RESOURCE_KIND_REGISTRY.values():
        assert spec.get_tool.startswith("rancher_")
        assert spec.get_tool.endswith("_get")
        assert spec.list_tool.startswith("rancher_")
        assert spec.list_tool.endswith("_list")
