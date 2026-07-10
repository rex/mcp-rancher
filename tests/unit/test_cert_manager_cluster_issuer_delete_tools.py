"""Curated cert-manager ClusterIssuer delete tool tests (destructive confirmation guard)."""

from __future__ import annotations

import pytest
from _cert_manager_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.cert_manager import (
    rancher_cert_manager_cluster_issuer_delete,
)


class StubCertManagerClusterIssuerDeleteClient:
    """Delete-capable stub for the cert_manager_cluster_issuer delete tests.

    Captures the most recent ``delete_json`` request path so tests can
    assert the route, then echoes a Kubernetes Status object back as the
    API server would on a successful CRD delete.  No namespace segment
    in the path — ClusterIssuer is cluster-scoped.
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

        del payload  # unused for k8s cluster_issuer deletes
        self.last_delete_path = path

        detail_path = "/k8s/clusters/local/apis/cert-manager.io/v1/clusterissuers/letsencrypt-prod"
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "letsencrypt-prod", "kind": "clusterissuers"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cert_manager_cluster_issuer_delete_refuses_wrong_confirmation() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call.

    Cluster-scoped: the phrase has no ``in namespace …`` suffix.
    """

    reset_rate_limit_state()
    client = StubCertManagerClusterIssuerDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_cert_manager_cluster_issuer_delete(
            cluster_issuer_name="letsencrypt-prod",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent can
    # recover by echoing it back on the next call.
    assert "delete cert_manager_cluster_issuer letsencrypt-prod" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_cert_manager_cluster_issuer_delete_routes_to_delete_json() -> None:
    """Correct confirmation phrase routes to delete_json on the cluster-scoped detail path."""

    reset_rate_limit_state()
    client = StubCertManagerClusterIssuerDeleteClient()

    result = await rancher_cert_manager_cluster_issuer_delete(
        cluster_issuer_name="letsencrypt-prod",
        confirmation="delete cert_manager_cluster_issuer letsencrypt-prod",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path has NO namespace segment — ClusterIssuer is cluster-scoped.
    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/cert-manager.io/v1/clusterissuers/letsencrypt-prod"
    )
    assert result.deleted is True
    assert result.resource_kind == "cert_manager_cluster_issuer"
    assert result.resource_name == "letsencrypt-prod"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == (
        "delete cert_manager_cluster_issuer letsencrypt-prod"
    )
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_cert_manager_cluster_issuers_list"]


@pytest.mark.asyncio
async def test_rancher_cert_manager_cluster_issuer_delete_emits_audit_on_both_paths() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_cert_manager_cluster_issuer_delete(
            cluster_issuer_name="letsencrypt-prod",
            confirmation="delete cert_manager_cluster_issuer letsencrypt-prod",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCertManagerClusterIssuerDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["tool_name"] == "rancher_cert_manager_cluster_issuer_delete"
    assert success_audits[0]["operation"] == "cert_manager_cluster_issuer_delete"
    assert success_audits[0]["plane"] == "steve"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_cert_manager_cluster_issuer_delete(
            cluster_issuer_name="letsencrypt-prod",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCertManagerClusterIssuerDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "cert_manager_cluster_issuer_delete"
    assert reject_audits[0]["outcome"] == "error"
    # Audit captures the rejection reason but never the wrong phrase value.
    assert "bad" not in reject_audits[0].get("arg_keys", [])
