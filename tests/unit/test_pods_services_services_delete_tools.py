"""Curated service delete tool tests."""

import pytest
from _pods_services_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.pods_services import rancher_service_delete

# rancher_service_delete
# =====================================================================


class StubServiceDeleteClient:
    """Delete-capable Steve stub for the service delete tests."""

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for delete requests."""

        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Delete tests do not need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Steve-shaped Status object."""

        del payload
        self.last_delete_path = path

        detail = "/services/demo/demo-service"
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-service", "kind": "services"},
            }
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_service_delete_refuses_wrong_confirmation_before_http() -> None:
    """Wrong confirmation phrase must raise before any HTTP call is made."""

    reset_rate_limit_state()
    client = StubServiceDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_service_delete(
            namespace="demo",
            service_name="demo-service",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete service demo-service in namespace demo" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_service_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the service detail path."""

    reset_rate_limit_state()
    client = StubServiceDeleteClient()

    result = await rancher_service_delete(
        namespace="demo",
        service_name="demo-service",
        confirmation="delete service demo-service in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == "/services/demo/demo-service"
    assert result.deleted is True
    assert result.resource_kind == "service"
    assert result.resource_name == "demo-service"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete service demo-service in namespace demo"
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_services_list"]


@pytest.mark.asyncio
async def test_rancher_service_delete_emits_audit_with_outcome() -> None:
    """Delete success and rejection both emit audit records."""

    reset_rate_limit_state()

    with capture_logs() as success_logs:
        await rancher_service_delete(
            namespace="demo",
            service_name="demo-service",
            confirmation="delete service demo-service in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "service_delete"
    assert success_audits[0]["outcome"] == "success"

    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_service_delete(
            namespace="demo",
            service_name="demo-service",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "service_delete"
    assert reject_audits[0]["outcome"] == "error"
