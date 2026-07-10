"""Curated LimitRange delete tool tests (destructive, end-to-end)."""

from __future__ import annotations

import pytest
from _governance_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.governance import rancher_limit_range_delete


class StubLimitRangeDeleteClient:
    """Delete-capable stub for LimitRange delete tests."""

    def __init__(self) -> None:
        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r}")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        del payload
        self.last_delete_path = path
        detail = "/k8s/clusters/local/api/v1/namespaces/demo/limitranges/demo-limits"
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-limits", "kind": "limitranges"},
            }
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_limit_range_delete_requires_exact_phrase() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubLimitRangeDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_limit_range_delete(
            namespace="demo",
            limit_range_name="demo-limits",
            confirmation="wrong",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete limit_range demo-limits in namespace demo" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_limit_range_delete_routes_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on detail path."""

    reset_rate_limit_state()
    client = StubLimitRangeDeleteClient()

    result = await rancher_limit_range_delete(
        namespace="demo",
        limit_range_name="demo-limits",
        confirmation="delete limit_range demo-limits in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/api/v1/namespaces/demo/limitranges/demo-limits"
    )
    assert result.deleted is True
    assert result.resource_kind == "limit_range"
    assert result.resource_name == "demo-limits"


@pytest.mark.asyncio
async def test_rancher_limit_range_delete_emits_audit_with_outcome() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()
    with capture_logs() as success_logs:
        await rancher_limit_range_delete(
            namespace="demo",
            limit_range_name="demo-limits",
            confirmation="delete limit_range demo-limits in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubLimitRangeDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "limit_range_delete"
    assert success_audits[0]["outcome"] == "success"

    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_limit_range_delete(
            namespace="demo",
            limit_range_name="demo-limits",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubLimitRangeDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "limit_range_delete"
    assert reject_audits[0]["outcome"] == "error"
