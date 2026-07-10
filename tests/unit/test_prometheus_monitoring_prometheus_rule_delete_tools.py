"""Curated PrometheusRule delete tool tests (destructive).

Covers PrometheusRule delete at ``monitoring.coreos.com/v1``.
"""

from __future__ import annotations

import pytest
from _prometheus_monitoring_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.prometheus_monitoring import rancher_prometheus_rule_delete


class StubPrometheusRuleDeleteClient:
    """Delete-capable raw Kubernetes proxy stub for the prometheus_rule delete tests.

    Captures the most recent ``delete_json`` path so tests can assert on the
    detail path, then returns a Kubernetes Status object on success.
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
        """Capture the delete path and return a Kubernetes Status object."""

        del payload  # unused for CRD deletes
        self.last_delete_path = path

        detail_path = (
            "/k8s/clusters/local/apis/monitoring.coreos.com/v1"
            "/namespaces/monitoring/prometheusrules/demo-rules"
        )
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-rules", "kind": "prometheusrules"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_prometheus_rule_delete_refuses_wrong_confirmation() -> None:
    """Wrong confirmation phrase must raise RancherCapabilityError before any HTTP call."""

    reset_rate_limit_state()
    client = StubPrometheusRuleDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_prometheus_rule_delete(
            namespace="monitoring",
            rule_name="demo-rules",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete prometheus_rule demo-rules in namespace monitoring" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_prometheus_rule_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubPrometheusRuleDeleteClient()

    result = await rancher_prometheus_rule_delete(
        namespace="monitoring",
        rule_name="demo-rules",
        confirmation="delete prometheus_rule demo-rules in namespace monitoring",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/monitoring.coreos.com/v1"
        "/namespaces/monitoring/prometheusrules/demo-rules"
    )
    assert result.deleted is True
    assert result.resource_kind == "prometheus_rule"
    assert result.resource_name == "demo-rules"
    assert result.namespace == "monitoring"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == (
        "delete prometheus_rule demo-rules in namespace monitoring"
    )
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_prometheus_rules_list"]


@pytest.mark.asyncio
async def test_rancher_prometheus_rule_delete_emits_audit_with_outcome() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_prometheus_rule_delete(
            namespace="monitoring",
            rule_name="demo-rules",
            confirmation="delete prometheus_rule demo-rules in namespace monitoring",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPrometheusRuleDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "prometheus_rule_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_prometheus_rule_delete(
            namespace="monitoring",
            rule_name="demo-rules",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPrometheusRuleDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "prometheus_rule_delete"
    assert reject_audits[0]["outcome"] == "error"
