"""Payload-trimming tests (ROADMAP K-2).

Curated responses drop the raw ``payload`` / ``response_payload`` from the
DUMP (the agent gets a small response, not a 15-31 KB firehose) while keeping
it on the model instance — so attribute access is unaffected and the ~120
existing attribute assertions still hold. The generic escape-hatch tools keep
the full payload.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.resources import GenericResourceDetail, RancherCuratedDeleteResult


class _CuratedDetail(RancherModel):
    """A curated detail model — inherits the default (hides payload in dump)."""

    serializer_hides_payload: ClassVar[bool] = True  # explicit for the reader

    name: str = "demo"
    payload: dict[str, object] = Field(default_factory=dict)


def test_curated_model_hides_payload_in_dump_but_keeps_attribute() -> None:
    model = _CuratedDetail(payload={"spec": {"blob": "x" * 5000}})

    # The attribute is intact — tests and downstream code still read it.
    assert model.payload["spec"] == {"blob": "x" * 5000}
    # ...but the dumped response the agent sees omits the raw blob entirely.
    assert "payload" not in model.model_dump(by_alias=True)
    assert "payload" not in model.model_dump()


def test_curated_delete_result_hides_response_payload() -> None:
    result = RancherCuratedDeleteResult(
        instance="work",
        plane="steve",
        resource_kind="Pod",
        resource_name="api-0",
        namespace="default",
        confirmation_phrase_used="delete pod api-0 in namespace default",
        response_payload={"kind": "Status", "managedFields": ["huge"] * 100},
    )

    assert result.response_payload["kind"] == "Status"  # attribute intact
    dumped = result.model_dump(by_alias=True)
    assert "responsePayload" not in dumped  # the 31 KB blob is gone
    assert dumped["deleted"] is True  # the small confirmation the operator wanted


def test_generic_escape_hatch_keeps_full_payload() -> None:
    detail = GenericResourceDetail(
        instance="work",
        plane="steve",
        schema_id="pod",
        plural_name="pods",
        resource_id="default/api-0",
        resource_path="/v1/pods/default/api-0",
        payload={"spec": {"nodeName": "node-1"}},
    )

    dumped = detail.model_dump(by_alias=True)
    assert dumped["payload"]["spec"]["nodeName"] == "node-1"
