"""Curated logging-pipeline delete tool tests (namespaced Output + Flow, destructive)."""

from __future__ import annotations

import pytest
from _logging_pipeline_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.logging_pipeline import (
    rancher_flow_delete,
    rancher_output_delete,
)

# =====================================================================
# rancher_output_delete end-to-end tests (D-3-output-delete)
# Block placed at END of file to avoid same-pack-pair conflicts with the
# parallel flow_delete agent in this batch.
# =====================================================================


class StubOutputDeleteClient:
    """Deterministic raw Kubernetes proxy stub for the output delete tests.

    Captures the most recent ``delete_json`` request so tests can assert
    on the namespaced detail path, then returns a Kubernetes Status
    object the way the real API server would.
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

        del payload  # unused for Banzai logging Output deletes
        self.last_delete_path = path

        detail_path = (
            "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1"
            "/namespaces/logging/outputs/s3-out"
        )
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "s3-out", "kind": "outputs"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_output_delete_refuses_wrong_confirmation_before_http() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call.

    The whole point of the confirmation phrase is that an agent (or
    user) can't accidentally delete a resource by guessing the tool's
    contract. The exact phrase must be echoed back.
    """

    reset_rate_limit_state()
    client = StubOutputDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_output_delete(
            namespace="logging",
            output_name="s3-out",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call.
    assert "delete output s3-out in namespace logging" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_output_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the namespaced detail path."""

    reset_rate_limit_state()
    client = StubOutputDeleteClient()

    result = await rancher_output_delete(
        namespace="logging",
        output_name="s3-out",
        confirmation="delete output s3-out in namespace logging",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/namespaces/logging/outputs/s3-out"
    )
    assert result.deleted is True
    assert result.resource_kind == "output"
    assert result.resource_name == "s3-out"
    assert result.namespace == "logging"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete output s3-out in namespace logging"
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_outputs_list"]


@pytest.mark.asyncio
async def test_rancher_output_delete_emits_audit_on_both_paths() -> None:
    """Delete success and rejection both write audit records with operation=output_delete."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_output_delete(
            namespace="logging",
            output_name="s3-out",
            confirmation="delete output s3-out in namespace logging",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubOutputDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["tool_name"] == "rancher_output_delete"
    assert success_audits[0]["operation"] == "output_delete"
    assert success_audits[0]["plane"] == "steve"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_output_delete(
            namespace="logging",
            output_name="s3-out",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubOutputDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["tool_name"] == "rancher_output_delete"
    assert reject_audits[0]["operation"] == "output_delete"
    assert reject_audits[0]["outcome"] == "error"
    # Audit captures the rejection reason but never the wrong phrase value.
    assert "bad" not in reject_audits[0].get("arg_keys", [])


# =====================================================================
# rancher_flow_delete tests (D-3-flow-delete)
# =====================================================================


class StubFlowDeleteClient:
    """Delete-capable raw Kubernetes proxy stub for the flow delete tests.

    Captures the most recent ``delete_json`` request path so tests can
    assert no HTTP call happened on a bad confirmation, then returns a
    Kubernetes Status object on a successful DELETE.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for delete requests."""

        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The delete tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Kubernetes Status object."""

        del payload  # unused for k8s flow deletes
        self.last_delete_path = path

        detail_path = (
            "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1"
            "/namespaces/logging/flows/app-flow"
        )
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "app-flow", "kind": "flows"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_flow_delete_refuses_wrong_confirmation_before_http() -> None:
    """Wrong confirmation phrase raises RancherCapabilityError before any HTTP call."""

    reset_rate_limit_state()
    client = StubFlowDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_flow_delete(
            namespace="logging",
            flow_name="app-flow",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call.
    assert "delete flow app-flow in namespace logging" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_flow_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubFlowDeleteClient()

    result = await rancher_flow_delete(
        namespace="logging",
        flow_name="app-flow",
        confirmation="delete flow app-flow in namespace logging",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/namespaces/logging/flows/app-flow"
    )
    assert result.deleted is True
    assert result.resource_kind == "flow"
    assert result.resource_name == "app-flow"
    assert result.namespace == "logging"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete flow app-flow in namespace logging"
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_flows_list"]


@pytest.mark.asyncio
async def test_rancher_flow_delete_emits_audit_on_both_paths() -> None:
    """Delete success and rejection both write audit records with operation=flow_delete."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_flow_delete(
            namespace="logging",
            flow_name="app-flow",
            confirmation="delete flow app-flow in namespace logging",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubFlowDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["tool_name"] == "rancher_flow_delete"
    assert success_audits[0]["operation"] == "flow_delete"
    assert success_audits[0]["plane"] == "steve"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_flow_delete(
            namespace="logging",
            flow_name="app-flow",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubFlowDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "flow_delete"
    assert reject_audits[0]["outcome"] == "error"
