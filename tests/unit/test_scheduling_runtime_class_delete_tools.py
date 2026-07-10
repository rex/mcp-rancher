"""Curated RuntimeClass delete tool tests (destructive, cluster-scoped)."""

from __future__ import annotations

import pytest
from _scheduling_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.scheduling import rancher_runtime_class_delete


class StubRuntimeClassDeleteClient:
    """Deterministic raw Kubernetes proxy stub for the runtime_class delete tests.

    Cluster-scoped: no namespace segment in the path. Captures the most
    recent ``delete_json`` request so tests can assert on the
    cluster-scoped detail path, then returns a Kubernetes Status object
    the way the real API server would.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for delete requests."""

        self.last_delete_path: str | None = None

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Kubernetes Status object."""

        del payload  # unused for RuntimeClass deletes
        self.last_delete_path = path

        detail_path = "/k8s/clusters/local/apis/node.k8s.io/v1/runtimeclasses/kata"
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "kata", "kind": "runtimeclasses"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_runtime_class_delete_refuses_wrong_confirmation_before_http() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call.

    The whole point of the confirmation phrase is that an agent (or
    user) can't accidentally delete a resource by guessing the tool's
    contract. The exact phrase must be echoed back.
    """

    reset_rate_limit_state()
    client = StubRuntimeClassDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_runtime_class_delete(
            runtime_class_name="kata",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call.
    assert "delete runtime_class kata" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_runtime_class_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the cluster-scoped detail path."""

    reset_rate_limit_state()
    client = StubRuntimeClassDeleteClient()

    result = await rancher_runtime_class_delete(
        runtime_class_name="kata",
        confirmation="delete runtime_class kata",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_delete_path == "/k8s/clusters/local/apis/node.k8s.io/v1/runtimeclasses/kata"
    assert result.deleted is True
    assert result.resource_kind == "runtime_class"
    assert result.resource_name == "kata"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete runtime_class kata"
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_runtime_classes_list"]


@pytest.mark.asyncio
async def test_rancher_runtime_class_delete_emits_audit_on_both_paths() -> None:
    """Delete success and rejection both write audit records with operation=runtime_class_delete."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_runtime_class_delete(
            runtime_class_name="kata",
            confirmation="delete runtime_class kata",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubRuntimeClassDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["tool_name"] == "rancher_runtime_class_delete"
    assert success_audits[0]["operation"] == "runtime_class_delete"
    assert success_audits[0]["plane"] == "steve"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_runtime_class_delete(
            runtime_class_name="kata",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubRuntimeClassDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["tool_name"] == "rancher_runtime_class_delete"
    assert reject_audits[0]["operation"] == "runtime_class_delete"
    assert reject_audits[0]["outcome"] == "error"
    # Audit captures the rejection reason but never the wrong phrase value.
    assert "bad" not in reject_audits[0].get("arg_keys", [])
