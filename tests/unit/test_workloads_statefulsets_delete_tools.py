"""Curated StatefulSet delete tool tests (destructive)."""

from __future__ import annotations

import pytest
from _workloads_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.workloads import rancher_statefulset_delete

# =====================================================================
# rancher_statefulset_delete (DESTRUCTIVE)
# =====================================================================


class StubStatefulSetDeleteClient:
    """Delete-capable stub for the StatefulSet delete tests."""

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

        detail = (
            "/k8s/clusters/venue-local/apis/apps/v1/namespaces/default/statefulsets/my-statefulset"
        )
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "my-statefulset", "kind": "statefulsets"},
            }
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_statefulset_delete_refuses_wrong_confirmation_before_http() -> None:
    """Wrong confirmation phrase must raise RancherCapabilityError with no HTTP call."""

    reset_rate_limit_state()
    client = StubStatefulSetDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_statefulset_delete(
            namespace="default",
            statefulset_name="my-statefulset",
            confirmation="wrong",
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete statefulset my-statefulset in namespace default" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_statefulset_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct phrase routes to delete_json on the statefulset detail path."""

    reset_rate_limit_state()
    client = StubStatefulSetDeleteClient()

    result = await rancher_statefulset_delete(
        namespace="default",
        statefulset_name="my-statefulset",
        confirmation="delete statefulset my-statefulset in namespace default",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/default/statefulsets/my-statefulset"
    )
    assert result.deleted is True
    assert result.resource_kind == "statefulset"
    assert result.resource_name == "my-statefulset"
    assert result.namespace == "default"
    assert result.cluster_id == "venue-local"
    assert result.suggested_next_steps == ["rancher_statefulsets_list"]


@pytest.mark.asyncio
async def test_rancher_statefulset_delete_emits_audit_with_outcome_success() -> None:
    """Audit record must carry operation='statefulset_delete' and outcome='success'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_statefulset_delete(
            namespace="default",
            statefulset_name="my-statefulset",
            confirmation="delete statefulset my-statefulset in namespace default",
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubStatefulSetDeleteClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_statefulset_delete"
    assert record["operation"] == "statefulset_delete"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
