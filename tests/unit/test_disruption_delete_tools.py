"""Curated PodDisruptionBudget delete tool tests (destructive)."""

from __future__ import annotations

import pytest
from _disruption_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.disruption import rancher_pod_disruption_budget_delete

# rancher_pod_disruption_budget_delete tests
# =====================================================================


class StubPdbDeleteClient:
    """Delete-capable raw Kubernetes proxy stub for the PDB delete tests.

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

        del payload  # unused for k8s PDB deletes
        self.last_delete_path = path

        detail_path = (
            "/k8s/clusters/local/apis/policy/v1/namespaces/demo/poddisruptionbudgets/demo-pdb"
        )
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-pdb", "kind": "poddisruptionbudgets"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_pod_disruption_budget_delete_refuses_wrong_confirmation() -> None:
    """Wrong confirmation phrase raises RancherCapabilityError before any HTTP call."""

    reset_rate_limit_state()
    client = StubPdbDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_pod_disruption_budget_delete(
            namespace="demo",
            budget_name="demo-pdb",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete pod_disruption_budget demo-pdb in namespace demo" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_pod_disruption_budget_delete_with_correct_phrase_succeeds() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubPdbDeleteClient()

    result = await rancher_pod_disruption_budget_delete(
        namespace="demo",
        budget_name="demo-pdb",
        confirmation="delete pod_disruption_budget demo-pdb in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert (
        client.last_delete_path
        == "/k8s/clusters/local/apis/policy/v1/namespaces/demo/poddisruptionbudgets/demo-pdb"
    )
    assert result.deleted is True
    assert result.resource_kind == "pod_disruption_budget"
    assert result.resource_name == "demo-pdb"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == (
        "delete pod_disruption_budget demo-pdb in namespace demo"
    )
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_pod_disruption_budgets_list"]


@pytest.mark.asyncio
async def test_rancher_pod_disruption_budget_delete_emits_audit_with_outcome() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_pod_disruption_budget_delete(
            namespace="demo",
            budget_name="demo-pdb",
            confirmation="delete pod_disruption_budget demo-pdb in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPdbDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "pod_disruption_budget_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_pod_disruption_budget_delete(
            namespace="demo",
            budget_name="demo-pdb",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPdbDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "pod_disruption_budget_delete"
    assert reject_audits[0]["outcome"] == "error"
