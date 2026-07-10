"""Curated pod delete tool tests."""

import pytest
from _pods_services_support import build_settings

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.pods_services import rancher_pod_delete

# rancher_pod_delete
# =====================================================================


class StubPodDeleteClient:
    """Delete-capable Steve stub for the pod delete tests."""

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

        detail = "/pods/demo/demo-pod"
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-pod", "kind": "pods"},
            }
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_pod_delete_refuses_wrong_confirmation_before_http() -> None:
    """Wrong confirmation phrase must raise before any HTTP call is made."""

    reset_rate_limit_state()
    client = StubPodDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_pod_delete(
            namespace="demo",
            pod_name="demo-pod",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete pod demo-pod in namespace demo" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_pod_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the pod detail path."""

    reset_rate_limit_state()
    client = StubPodDeleteClient()

    result = await rancher_pod_delete(
        namespace="demo",
        pod_name="demo-pod",
        confirmation="delete pod demo-pod in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == "/pods/demo/demo-pod"
    assert result.deleted is True
    assert result.resource_kind == "pod"
    assert result.resource_name == "demo-pod"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete pod demo-pod in namespace demo"
    assert result.response_payload["kind"] == "Status"
    assert result.suggested_next_steps == ["rancher_pods_list"]
