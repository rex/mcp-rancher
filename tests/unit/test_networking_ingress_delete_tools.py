"""Curated ingress delete tool tests (destructive)."""

from __future__ import annotations

import pytest
from _networking_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.networking import rancher_ingress_delete

# =====================================================================
# rancher_ingress_delete (DeleteConfig substrate)
# =====================================================================


class StubIngressDeleteClient:
    """Delete-capable stub for the ingress delete tests."""

    def __init__(self) -> None:
        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        del payload
        self.last_delete_path = path
        expected_path = (
            "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/ingresses/demo-ingress"
        )
        if path == expected_path:
            return {"kind": "Status", "apiVersion": "v1", "status": "Success"}
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_ingress_delete_refuses_wrong_confirmation_before_http() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubIngressDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_ingress_delete(
            namespace="demo",
            ingress_name="demo-ingress",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete ingress demo-ingress in namespace demo" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_ingress_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubIngressDeleteClient()

    result = await rancher_ingress_delete(
        namespace="demo",
        ingress_name="demo-ingress",
        confirmation="delete ingress demo-ingress in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert (
        client.last_delete_path
        == "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/ingresses/demo-ingress"
    )
    assert result.deleted is True
    assert result.resource_kind == "ingress"
    assert result.resource_name == "demo-ingress"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_ingress_delete_emits_audit_with_outcome() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()
    with capture_logs() as success_logs:
        await rancher_ingress_delete(
            namespace="demo",
            ingress_name="demo-ingress",
            confirmation="delete ingress demo-ingress in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubIngressDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "ingress_delete"
    assert success_audits[0]["outcome"] == "success"

    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_ingress_delete(
            namespace="demo",
            ingress_name="demo-ingress",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubIngressDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "ingress_delete"
    assert reject_audits[0]["outcome"] == "error"
