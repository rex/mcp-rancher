"""Curated network policy delete tool tests (destructive)."""

from __future__ import annotations

import pytest
from _networking_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.networking import rancher_network_policy_delete

# =====================================================================
# rancher_network_policy_delete end-to-end tests
# =====================================================================


class StubNetworkPolicyDeleteClient:
    """Delete-capable raw Kubernetes proxy stub for the network_policy delete tests.

    Captures the most recent ``delete_json`` request so tests can
    assert on the path, then returns a realistic Kubernetes Status object.
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

        del payload  # unused for k8s networkpolicy deletes
        self.last_delete_path = path

        detail_path = (
            "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/networkpolicies/deny-all"
        )
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "deny-all", "kind": "networkpolicies"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_network_policy_delete_requires_exact_confirmation_phrase() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call.

    The whole point of the confirmation phrase is that an agent (or
    user) can't accidentally delete a resource by guessing the tool's
    contract. The exact phrase must be echoed back.
    """

    reset_rate_limit_state()
    client = StubNetworkPolicyDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_network_policy_delete(
            namespace="demo",
            network_policy_name="deny-all",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call.
    assert "delete network_policy deny-all in namespace demo" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_network_policy_delete_with_correct_phrase_succeeds() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubNetworkPolicyDeleteClient()

    result = await rancher_network_policy_delete(
        namespace="demo",
        network_policy_name="deny-all",
        confirmation="delete network_policy deny-all in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/networkpolicies/deny-all"
    )
    assert result.deleted is True
    assert result.resource_kind == "network_policy"
    assert result.resource_name == "deny-all"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == ("delete network_policy deny-all in namespace demo")
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_network_policies_list"]


@pytest.mark.asyncio
async def test_rancher_network_policy_delete_emits_audit_with_delete_op() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_network_policy_delete(
            namespace="demo",
            network_policy_name="deny-all",
            confirmation="delete network_policy deny-all in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubNetworkPolicyDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "network_policy_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_network_policy_delete(
            namespace="demo",
            network_policy_name="deny-all",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubNetworkPolicyDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "network_policy_delete"
    assert reject_audits[0]["outcome"] == "error"


@pytest.mark.asyncio
async def test_rancher_network_policy_delete_refuses_read_only_instance() -> None:
    """Read-only instances must refuse delete even with valid confirmation."""

    reset_rate_limit_state()
    read_only_settings = AppSettings(
        RANCHER_DEFAULT_INSTANCE="locked",
        RANCHER_INSTANCES_JSON=(
            '{"locked":{"url":"https://rancher.example.com","token":"token-x:secret",'
            '"verify_ssl":true,"read_only":true}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )

    with pytest.raises(RancherCapabilityError):
        await rancher_network_policy_delete(
            namespace="demo",
            network_policy_name="deny-all",
            confirmation="delete network_policy deny-all in namespace demo",
            cluster_id="local",
            instance="locked",
            settings=read_only_settings,
            client=StubNetworkPolicyDeleteClient(),
        )
