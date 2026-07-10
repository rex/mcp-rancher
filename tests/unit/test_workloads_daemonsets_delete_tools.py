"""Curated DaemonSet delete tool tests (destructive)."""

from __future__ import annotations

import pytest
from _workloads_support import build_settings

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.workloads import rancher_daemonset_delete

# =====================================================================
# rancher_daemonset_delete (DESTRUCTIVE substrate — D-3-daemonset-delete)
# =====================================================================


class StubDaemonSetDeleteClient:
    """Delete-capable stub for the DaemonSet delete tests."""

    def __init__(self) -> None:
        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r}")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        del payload
        self.last_delete_path = path

        detail = "/k8s/clusters/venue-local/apis/apps/v1/namespaces/kube-system/daemonsets/kindnet"
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "kindnet", "kind": "daemonsets"},
            }
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_daemonset_delete_requires_phrase_with_substituted_values() -> None:
    """Delete substrate generalizes — same confirmation-phrase guard pattern as deployment."""

    reset_rate_limit_state()
    client = StubDaemonSetDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_daemonset_delete(
            namespace="kube-system",
            daemonset_name="kindnet",
            confirmation="wrong",
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete daemonset kindnet in namespace kube-system" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_daemonset_delete_with_correct_phrase_succeeds() -> None:
    """Correct phrase routes to delete_json on the daemonset detail path."""

    reset_rate_limit_state()
    client = StubDaemonSetDeleteClient()

    result = await rancher_daemonset_delete(
        namespace="kube-system",
        daemonset_name="kindnet",
        confirmation="delete daemonset kindnet in namespace kube-system",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/kube-system/daemonsets/kindnet"
    )
    assert result.deleted is True
    assert result.resource_kind == "daemonset"
    assert result.resource_name == "kindnet"
    assert result.namespace == "kube-system"
    assert result.cluster_id == "venue-local"
    assert result.suggested_next_steps == ["rancher_daemonsets_list"]
