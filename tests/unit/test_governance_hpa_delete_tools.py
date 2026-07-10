"""Curated HPA delete tool tests (destructive, end-to-end)."""

from __future__ import annotations

import pytest
from _governance_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.governance import rancher_horizontal_pod_autoscaler_delete


class StubHpaDeleteClient:
    """Delete-capable raw Kubernetes proxy stub for HPA delete tests.

    Captures the most recent ``delete_json`` request so tests can assert on
    the delete path, then returns a Kubernetes Status object.
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

        del payload  # unused for k8s HPA deletes
        self.last_delete_path = path

        detail_path = (
            "/k8s/clusters/local/apis/autoscaling/v2"
            "/namespaces/demo/horizontalpodautoscalers/demo-hpa"
        )
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-hpa", "kind": "horizontalpodautoscalers"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_delete_requires_exact_phrase() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubHpaDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_horizontal_pod_autoscaler_delete(
            namespace="demo",
            hpa_name="demo-hpa",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete horizontal_pod_autoscaler demo-hpa in namespace demo" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_delete_with_correct_phrase_succeeds() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubHpaDeleteClient()

    result = await rancher_horizontal_pod_autoscaler_delete(
        namespace="demo",
        hpa_name="demo-hpa",
        confirmation="delete horizontal_pod_autoscaler demo-hpa in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/autoscaling/v2/namespaces/demo/horizontalpodautoscalers/demo-hpa"
    )
    assert result.deleted is True
    assert result.resource_kind == "horizontal_pod_autoscaler"
    assert result.resource_name == "demo-hpa"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == (
        "delete horizontal_pod_autoscaler demo-hpa in namespace demo"
    )
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_horizontal_pod_autoscalers_list"]


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_delete_emits_audit() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    with capture_logs() as success_logs:
        await rancher_horizontal_pod_autoscaler_delete(
            namespace="demo",
            hpa_name="demo-hpa",
            confirmation="delete horizontal_pod_autoscaler demo-hpa in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubHpaDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "hpa_delete"
    assert success_audits[0]["outcome"] == "success"

    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_horizontal_pod_autoscaler_delete(
            namespace="demo",
            hpa_name="demo-hpa",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubHpaDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "hpa_delete"
    assert reject_audits[0]["outcome"] == "error"


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_delete_refuses_read_only_instance() -> None:
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
    client = StubHpaDeleteClient()

    with pytest.raises(RancherCapabilityError):
        await rancher_horizontal_pod_autoscaler_delete(
            namespace="demo",
            hpa_name="demo-hpa",
            confirmation="delete horizontal_pod_autoscaler demo-hpa in namespace demo",
            cluster_id="local",
            instance="locked",
            settings=read_only_settings,
            client=client,
        )

    assert client.last_delete_path is None
