"""Curated cert-manager Certificate delete tool tests (destructive confirmation guard)."""

from __future__ import annotations

import pytest
from _cert_manager_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.cert_manager import (
    rancher_cert_manager_certificate_delete,
)


class StubCertManagerCertificateDeleteClient:
    """Delete-capable stub for the cert_manager_certificate delete tests.

    Captures the most recent ``delete_json`` request path so tests can
    assert the route, then echoes a Kubernetes Status object back as
    the API server would on a successful CRD delete.
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

        del payload
        self.last_delete_path = path
        expected_path = (
            "/k8s/clusters/local/apis/cert-manager.io/v1/namespaces/demo/certificates/demo-cert"
        )
        if path == expected_path:
            assert params is None
            return {"kind": "Status", "apiVersion": "v1", "status": "Success"}
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cert_manager_certificate_delete_refuses_wrong_confirmation() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubCertManagerCertificateDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_cert_manager_certificate_delete(
            namespace="demo",
            certificate_name="demo-cert",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete cert_manager_certificate demo-cert in namespace demo" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_cert_manager_certificate_delete_routes_to_delete_json() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubCertManagerCertificateDeleteClient()

    result = await rancher_cert_manager_certificate_delete(
        namespace="demo",
        certificate_name="demo-cert",
        confirmation="delete cert_manager_certificate demo-cert in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/cert-manager.io/v1/namespaces/demo/certificates/demo-cert"
    )
    assert result.deleted is True
    assert result.resource_kind == "cert_manager_certificate"
    assert result.resource_name == "demo-cert"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == (
        "delete cert_manager_certificate demo-cert in namespace demo"
    )
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_cert_manager_certificates_list"]


@pytest.mark.asyncio
async def test_rancher_cert_manager_certificate_delete_emits_audit_with_outcome() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_cert_manager_certificate_delete(
            namespace="demo",
            certificate_name="demo-cert",
            confirmation="delete cert_manager_certificate demo-cert in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCertManagerCertificateDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "cert_manager_certificate_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_cert_manager_certificate_delete(
            namespace="demo",
            certificate_name="demo-cert",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCertManagerCertificateDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "cert_manager_certificate_delete"
    assert reject_audits[0]["outcome"] == "error"
