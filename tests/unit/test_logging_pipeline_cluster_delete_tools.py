"""Curated cluster-scoped logging-pipeline delete tool tests (destructive)."""

from __future__ import annotations

import pytest
from _logging_pipeline_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.logging_pipeline import (
    rancher_cluster_flow_delete,
    rancher_cluster_output_delete,
)

# =====================================================================
# rancher_cluster_output_delete end-to-end tests (D-3-cluster-output-delete)
# Block placed at END of file to avoid same-pack-pair conflicts with the
# parallel cluster_flow_delete agent in this batch.
# =====================================================================


class StubClusterOutputDeleteClient:
    """Delete-capable raw Kubernetes proxy stub for the cluster_output delete tests.

    Captures the most recent ``delete_json`` request path so tests can
    assert no HTTP call happened on a bad confirmation, then returns a
    Kubernetes Status object on a successful DELETE. ClusterOutput is
    cluster-scoped (no namespace in the path).
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

        del payload  # unused for Banzai logging ClusterOutput deletes
        self.last_delete_path = path

        detail_path = (
            "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/clusteroutputs/cluster-s3-out"
        )
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "cluster-s3-out", "kind": "clusteroutputs"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cluster_output_delete_refuses_wrong_confirmation_before_http() -> None:
    """Wrong confirmation phrase raises RancherCapabilityError before any HTTP call."""

    reset_rate_limit_state()
    client = StubClusterOutputDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_cluster_output_delete(
            cluster_output_name="cluster-s3-out",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call. Cluster-scoped:
    # no "in namespace ..." suffix.
    assert "delete cluster_output cluster-s3-out" in str(excinfo.value)
    assert "namespace" not in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_cluster_output_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the cluster-scoped detail path."""

    reset_rate_limit_state()
    client = StubClusterOutputDeleteClient()

    result = await rancher_cluster_output_delete(
        cluster_output_name="cluster-s3-out",
        confirmation="delete cluster_output cluster-s3-out",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/clusteroutputs/cluster-s3-out"
    )
    assert result.deleted is True
    assert result.resource_kind == "cluster_output"
    assert result.resource_name == "cluster-s3-out"
    # Cluster-scoped: namespace is None on the typed result.
    assert result.namespace is None
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete cluster_output cluster-s3-out"
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_cluster_outputs_list"]


@pytest.mark.asyncio
async def test_rancher_cluster_output_delete_emits_audit_on_both_paths() -> None:
    """Both success and rejection write audit records with operation=cluster_output_delete."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_cluster_output_delete(
            cluster_output_name="cluster-s3-out",
            confirmation="delete cluster_output cluster-s3-out",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubClusterOutputDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["tool_name"] == "rancher_cluster_output_delete"
    assert success_audits[0]["operation"] == "cluster_output_delete"
    assert success_audits[0]["plane"] == "steve"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_cluster_output_delete(
            cluster_output_name="cluster-s3-out",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubClusterOutputDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["tool_name"] == "rancher_cluster_output_delete"
    assert reject_audits[0]["operation"] == "cluster_output_delete"
    assert reject_audits[0]["outcome"] == "error"
    # Audit captures the rejection reason but never the wrong phrase value.
    assert "bad" not in reject_audits[0].get("arg_keys", [])


class StubClusterFlowDeleteClient:
    """Delete-capable raw Kubernetes proxy stub for cluster_flow delete tests.

    Captures the most recent ``delete_json`` request path so tests can
    assert no HTTP call happened on a bad confirmation, then returns a
    Kubernetes Status object on a successful DELETE. The detail path is
    cluster-scoped — no ``/namespaces/<ns>`` segment.
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

        del payload  # unused for k8s cluster_flow deletes
        self.last_delete_path = path

        detail_path = (
            "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/clusterflows/demo-cflow"
        )
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-cflow", "kind": "clusterflows"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cluster_flow_delete_refuses_wrong_confirmation_before_http() -> None:
    """Wrong confirmation phrase raises RancherCapabilityError before any HTTP call."""

    reset_rate_limit_state()
    client = StubClusterFlowDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_cluster_flow_delete(
            cluster_flow_name="demo-cflow",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call. The phrase is
    # cluster-scoped — no `in namespace ...` suffix.
    assert "delete cluster_flow demo-cflow" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_cluster_flow_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the cluster-scoped detail path."""

    reset_rate_limit_state()
    client = StubClusterFlowDeleteClient()

    result = await rancher_cluster_flow_delete(
        cluster_flow_name="demo-cflow",
        confirmation="delete cluster_flow demo-cflow",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path has no /namespaces/<ns> segment.
    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/clusterflows/demo-cflow"
    )
    assert result.deleted is True
    assert result.resource_kind == "cluster_flow"
    assert result.resource_name == "demo-cflow"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete cluster_flow demo-cflow"
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_cluster_flows_list"]


@pytest.mark.asyncio
async def test_rancher_cluster_flow_delete_emits_audit_on_both_paths() -> None:
    """Delete success and rejection both write audit records with operation=cluster_flow_delete."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_cluster_flow_delete(
            cluster_flow_name="demo-cflow",
            confirmation="delete cluster_flow demo-cflow",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubClusterFlowDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["tool_name"] == "rancher_cluster_flow_delete"
    assert success_audits[0]["operation"] == "cluster_flow_delete"
    assert success_audits[0]["plane"] == "steve"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_cluster_flow_delete(
            cluster_flow_name="demo-cflow",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubClusterFlowDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "cluster_flow_delete"
    assert reject_audits[0]["outcome"] == "error"
