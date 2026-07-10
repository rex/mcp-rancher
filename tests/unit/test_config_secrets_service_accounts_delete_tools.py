"""Curated ServiceAccount delete tool tests."""

from __future__ import annotations

import pytest
from _config_secrets_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.config_secrets import rancher_service_account_delete

# =====================================================================
# rancher_service_account_delete end-to-end tests
# =====================================================================


class StubServiceAccountDeleteClient:
    """Delete-capable raw Kubernetes proxy stub for service_account delete tests.

    Captures ``last_delete_path`` so tests can assert no HTTP call fired
    on rejection paths and the correct detail path fired on success.
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

        del payload  # unused for k8s service_account deletes
        self.last_delete_path = path

        sa_detail = "/k8s/clusters/local/api/v1/namespaces/demo/serviceaccounts/demo-sa"
        if path == sa_detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-sa", "kind": "serviceaccounts"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_service_account_delete_requires_exact_confirmation_phrase() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call.

    The whole point of the confirmation phrase is that an agent (or
    user) can't accidentally delete a resource by guessing the tool's
    contract. The exact phrase must be echoed back.
    """

    reset_rate_limit_state()
    client = StubServiceAccountDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_service_account_delete(
            namespace="demo",
            service_account_name="demo-sa",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call.
    assert "delete service_account demo-sa in namespace demo" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_service_account_delete_with_correct_phrase_succeeds() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubServiceAccountDeleteClient()

    result = await rancher_service_account_delete(
        namespace="demo",
        service_account_name="demo-sa",
        confirmation="delete service_account demo-sa in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert (
        client.last_delete_path
        == "/k8s/clusters/local/api/v1/namespaces/demo/serviceaccounts/demo-sa"
    )
    assert result.deleted is True
    assert result.resource_kind == "service_account"
    assert result.resource_name == "demo-sa"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == ("delete service_account demo-sa in namespace demo")
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_service_accounts_list"]


@pytest.mark.asyncio
async def test_rancher_service_account_delete_emits_audit_with_delete_op() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_service_account_delete(
            namespace="demo",
            service_account_name="demo-sa",
            confirmation="delete service_account demo-sa in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceAccountDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "service_account_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_service_account_delete(
            namespace="demo",
            service_account_name="demo-sa",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceAccountDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "service_account_delete"
    assert reject_audits[0]["outcome"] == "error"
    # Audit captures the rejection reason but never the wrong phrase value.
    assert "bad" not in reject_audits[0].get("arg_keys", [])
