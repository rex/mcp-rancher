"""Envelope-shaping tests (ROADMAP L-0 / ADR-0002).

The base serializer strips universal noise from the DUMP: ``suggestedNextSteps``
is deleted outright, plumbing keys and empty ``[]``/``{}``/``None`` values are
omitted, falsy scalars are kept, and the raw ``payload`` blob on generic
escape-hatch models is preserved verbatim (only secret-scrubbed).
"""

from __future__ import annotations

from pydantic import Field

from rancher_mcp.envelope import shape_envelope
from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.resources import GenericResourceDetail


class _Curated(RancherModel):
    """A curated model — payload hidden, envelope shaped."""

    name: str = "demo"
    ready: bool = False
    replicas: int = 0
    note: str = ""
    issues: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    detail: str | None = None


def test_suggested_next_steps_always_dropped() -> None:
    # Empty (the common case) and populated (bare names) both vanish.
    assert "suggestedNextSteps" not in _Curated().model_dump(by_alias=True)
    populated = _Curated(suggested_next_steps=["rancher_cluster_get"])
    assert "suggestedNextSteps" not in populated.model_dump(by_alias=True)
    assert "suggested_next_steps" not in populated.model_dump()


def test_empty_values_dropped_but_falsy_scalars_kept() -> None:
    dumped = _Curated().model_dump(by_alias=True)
    # Empty list / dict / None are omitted.
    assert "issues" not in dumped
    assert "labels" not in dumped
    assert "detail" not in dumped
    # Falsy scalars carry meaning — kept.
    assert dumped["ready"] is False
    assert dumped["replicas"] == 0
    assert dumped["note"] == ""
    assert dumped["name"] == "demo"


def test_non_empty_values_survive() -> None:
    dumped = _Curated(issues=["boom"], labels={"a": "b"}, detail="x").model_dump(by_alias=True)
    assert dumped["issues"] == ["boom"]
    assert dumped["labels"] == {"a": "b"}
    assert dumped["detail"] == "x"


def test_plumbing_keys_stripped_at_any_depth() -> None:
    payload = {
        "name": "keep",
        "managedFields": ["huge"],
        "resourceVersion": "12345",
        "uid": "abc",
        "links": {"self": "/v1/x"},
        "nested": {"generation": 4, "baseType": "pod", "real": "value"},
    }
    shaped = shape_envelope(payload)
    assert shaped == {"name": "keep", "nested": {"real": "value"}}


def test_generic_payload_preserved_verbatim() -> None:
    # The escape hatch must return the raw object faithfully — empty children
    # inside the payload are NOT collapsed.
    detail = GenericResourceDetail(
        instance="work",
        plane="steve",
        schema_id="pod",
        plural_name="pods",
        resource_id="default/api-0",
        resource_path="/v1/pods/default/api-0",
        payload={"spec": {"nodeName": "node-1"}, "status": {}, "finalizers": []},
    )
    dumped = detail.model_dump(by_alias=True)
    assert dumped["payload"] == {"spec": {"nodeName": "node-1"}, "status": {}, "finalizers": []}


def test_shape_is_pure() -> None:
    original = {"a": None, "b": [], "keep": 1, "suggestedNextSteps": []}
    shape_envelope(original)
    assert original == {"a": None, "b": [], "keep": 1, "suggestedNextSteps": []}
