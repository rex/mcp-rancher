"""Curated PolicyReport delete tool tests (PolicyReport, ClusterPolicyReport)."""

from __future__ import annotations

import pytest
from _policy_reports_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.policy_reports import (
    rancher_cluster_policy_report_delete,
    rancher_policy_report_delete,
)

# =====================================================================
# rancher_policy_report_delete (DeleteConfig substrate)
# =====================================================================


class StubPolicyReportDeleteClient:
    """Deterministic raw Kubernetes proxy client for PolicyReport delete tests."""

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

        del payload  # unused for k8s policy_report deletes
        self.last_delete_path = path

        detail = (
            "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2/"
            "namespaces/demo/policyreports/demo-report"
        )
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-report", "kind": "policyreports"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_policy_report_delete_requires_exact_confirmation_phrase() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubPolicyReportDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_policy_report_delete(
            namespace="demo",
            report_name="demo-report",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call.
    assert "delete policy_report demo-report in namespace demo" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_policy_report_delete_with_correct_phrase_succeeds() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubPolicyReportDeleteClient()

    result = await rancher_policy_report_delete(
        namespace="demo",
        report_name="demo-report",
        confirmation="delete policy_report demo-report in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2/namespaces/demo/policyreports/demo-report"
    )
    assert result.deleted is True
    assert result.resource_kind == "policy_report"
    assert result.resource_name == "demo-report"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == ("delete policy_report demo-report in namespace demo")
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_policy_reports_list"]


@pytest.mark.asyncio
async def test_rancher_policy_report_delete_emits_audit_with_delete_op() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_policy_report_delete(
            namespace="demo",
            report_name="demo-report",
            confirmation="delete policy_report demo-report in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPolicyReportDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "policy_report_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_policy_report_delete(
            namespace="demo",
            report_name="demo-report",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPolicyReportDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "policy_report_delete"
    assert reject_audits[0]["outcome"] == "error"
    # Audit captures the rejection reason but never the wrong phrase value.
    assert "bad" not in reject_audits[0].get("arg_keys", [])


# =====================================================================
# rancher_cluster_policy_report_delete (cluster-scoped, no namespace)
# =====================================================================


class StubClusterPolicyReportDeleteClient:
    """Deterministic raw Kubernetes proxy client for ClusterPolicyReport delete tests."""

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

        del payload  # unused for k8s cluster_policy_report deletes
        self.last_delete_path = path

        detail = (
            "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2/clusterpolicyreports/system-report"
        )
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "system-report", "kind": "clusterpolicyreports"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cluster_policy_report_delete_requires_exact_confirmation_phrase() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubClusterPolicyReportDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_cluster_policy_report_delete(
            report_name="system-report",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call. Cluster-scoped:
    # no namespace appears in the phrase.
    assert "delete cluster_policy_report system-report" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_cluster_policy_report_delete_with_correct_phrase_succeeds() -> None:
    """Correct confirmation phrase routes to delete_json on the cluster-scoped detail path."""

    reset_rate_limit_state()
    client = StubClusterPolicyReportDeleteClient()

    result = await rancher_cluster_policy_report_delete(
        report_name="system-report",
        confirmation="delete cluster_policy_report system-report",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2/clusterpolicyreports/system-report"
    )
    assert result.deleted is True
    assert result.resource_kind == "cluster_policy_report"
    assert result.resource_name == "system-report"
    # Cluster-scoped resource: namespace is absent from the result.
    assert result.namespace is None
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete cluster_policy_report system-report"
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_cluster_policy_reports_list"]


@pytest.mark.asyncio
async def test_rancher_cluster_policy_report_delete_emits_audit_with_delete_op() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_cluster_policy_report_delete(
            report_name="system-report",
            confirmation="delete cluster_policy_report system-report",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubClusterPolicyReportDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "cluster_policy_report_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_cluster_policy_report_delete(
            report_name="system-report",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubClusterPolicyReportDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "cluster_policy_report_delete"
    assert reject_audits[0]["outcome"] == "error"
    # Audit captures the rejection reason but never the wrong phrase value.
    assert "bad" not in reject_audits[0].get("arg_keys", [])
