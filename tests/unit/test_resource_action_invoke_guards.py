"""The generic action tools are mutations, and are guarded like one.

``rancher_{norman,steve}_resource_action_invoke`` POST an arbitrary Rancher
action. Until 2026-11-15 neither checked whether the instance was read-only,
neither was audited and neither was rate limited — see
``tests/unit/test_write_guards_fleet_wide.py`` for the gate that now asks that
of every tool, and ``docs/adr/0003-write-guards.md`` for the account.

These are the per-tool details the fleet-wide gate does not look at: that the
refusal happens before the client is touched at all, and that the audit record
says *which* action was invoked.
"""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError, RancherRateLimitError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.resources import (
    rancher_norman_resource_action_invoke,
    rancher_steve_resource_action_invoke,
)


def build_settings(*, read_only: bool = False, write_rate: int = 60) -> AppSettings:
    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            f'"verify_ssl":true,"read_only":{str(read_only).lower()}}}}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
        RANCHER_MCP_WRITE_RATE_LIMIT_PER_MIN=write_rate,
    )


class Tripwire:
    """A client that must not be used. Any request is the defect."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"GET {path} was sent before the write guards ran")

    async def get_text(self, path: str, params: object = None) -> str:
        raise AssertionError(f"GET {path} was sent before the write guards ran")

    async def post_json(
        self, path: str, payload: object = None, params: object = None
    ) -> dict[str, object]:
        raise AssertionError(f"POST {path} was sent before the write guards ran")


class StubNorman:
    """Just enough Norman to invoke one action on one cluster."""

    def __init__(self) -> None:
        self.posted: list[tuple[str, object]] = []

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        if path == "/v3/schemas/cluster":
            return {
                "id": "cluster",
                "pluralName": "clusters",
                "links": {"collection": "https://rancher.work.example.com/v3/clusters"},
            }
        return {
            "id": "c-abc",
            "type": "cluster",
            "actions": {
                "rotateCertificates": (
                    "https://rancher.work.example.com/v3/clusters/c-abc?action=rotateCertificates"
                )
            },
            "links": {"self": "https://rancher.work.example.com/v3/clusters/c-abc"},
        }

    async def post_json(
        self, path: str, payload: object = None, params: object = None
    ) -> dict[str, object]:
        self.posted.append((path, payload))
        return {"message": "rotating"}


@pytest.fixture(autouse=True)
def _fresh_write_bucket() -> None:  # pyright: ignore[reportUnusedFunction]
    reset_rate_limit_state()


async def test_a_read_only_instance_refuses_a_norman_action_before_any_request() -> None:
    with capture_logs() as logs, pytest.raises(RancherCapabilityError, match="read-only"):
        await rancher_norman_resource_action_invoke(
            schema_id="cluster",
            resource_id="c-abc",
            action_name="rotateCertificates",
            settings=build_settings(read_only=True),
            client=Tripwire(),
        )

    audit = [record for record in logs if record["event"] == "audit"]
    assert len(audit) == 1
    assert audit[0]["outcome"] == "error"
    assert audit[0]["action_name"] == "rotateCertificates"


async def test_a_read_only_instance_refuses_a_steve_action_before_any_request() -> None:
    with capture_logs() as logs, pytest.raises(RancherCapabilityError, match="read-only"):
        await rancher_steve_resource_action_invoke(
            schema_id="pod",
            resource_id="web-0",
            action_name="restart",
            cluster_id="c-m-abc",
            namespace="shop",
            settings=build_settings(read_only=True),
            steve_client=Tripwire(),
            management_client=Tripwire(),
        )

    audit = [record for record in logs if record["event"] == "audit"]
    assert len(audit) == 1
    assert audit[0]["outcome"] == "error"
    assert audit[0]["plane"] == "steve"
    assert audit[0]["cluster_id"] == "c-m-abc"


async def test_an_invoked_action_is_audited_by_name_and_never_by_payload() -> None:
    client = StubNorman()

    with capture_logs() as logs:
        await rancher_norman_resource_action_invoke(
            schema_id="cluster",
            resource_id="c-abc",
            action_name="rotateCertificates",
            payload_json='{"caCertificates": "do-not-log-me"}',
            settings=build_settings(),
            client=client,
        )

    assert [path for path, _ in client.posted] == ["/v3/clusters/c-abc?action=rotateCertificates"]
    audit = [record for record in logs if record["event"] == "audit"]
    assert len(audit) == 1
    record = audit[0]
    assert record["operation"] == "action_invoke"
    assert record["plane"] == "norman"
    assert record["outcome"] == "success"
    assert record["action_name"] == "rotateCertificates"
    assert record["schema_id"] == "cluster"
    assert record["resource_id"] == "c-abc"
    assert "payload_json" in record["arg_keys"]
    assert "do-not-log-me" not in repr(record), "an argument VALUE reached the audit record"


async def test_an_action_counts_against_the_write_rate_limit() -> None:
    settings = build_settings(write_rate=1)  # burst capacity of two

    for _ in range(2):
        await rancher_norman_resource_action_invoke(
            schema_id="cluster",
            resource_id="c-abc",
            action_name="rotateCertificates",
            settings=settings,
            client=StubNorman(),
        )

    with pytest.raises(RancherRateLimitError):
        await rancher_norman_resource_action_invoke(
            schema_id="cluster",
            resource_id="c-abc",
            action_name="rotateCertificates",
            settings=settings,
            client=Tripwire(),
        )
