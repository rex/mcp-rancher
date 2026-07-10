"""Curated DaemonSet tool tests (list/get)."""

from __future__ import annotations

import pytest
from _workloads_support import (
    StubRawK8sClient,
    build_settings,
)

from rancher_mcp.tools.workloads import (
    rancher_daemonset_get,
    rancher_daemonsets_list,
)


@pytest.mark.asyncio
async def test_rancher_daemonsets_list_returns_typed_summaries() -> None:
    """Curated daemonset list should expose scheduling-aware summaries."""

    result = await rancher_daemonsets_list(
        namespace="kube-system",
        cluster_id="venue-local",
        ready=True,
        limit=3,
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.daemonset_count == 1
    assert result.daemonsets[0].name == "kindnet"
    assert result.daemonsets[0].ready is True


@pytest.mark.asyncio
async def test_rancher_daemonsets_list_filters_not_ready_items() -> None:
    """Curated daemonset list should apply the computed readiness filter."""

    class MixedDaemonSetClient:
        """Return ready and not-ready daemonsets."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic daemonset collection."""

            assert (
                path == "/k8s/clusters/venue-local/apis/apps/v1/namespaces/kube-system/daemonsets"
            )
            assert params is None
            return {
                "items": [
                    {
                        "metadata": {"name": "ready-daemonset", "namespace": "kube-system"},
                        "spec": {
                            "template": {"spec": {"containers": [{"name": "app", "image": "demo"}]}}
                        },
                        "status": {
                            "desiredNumberScheduled": 2,
                            "numberReady": 2,
                            "updatedNumberScheduled": 2,
                        },
                    },
                    {
                        "metadata": {"name": "not-ready-daemonset", "namespace": "kube-system"},
                        "spec": {
                            "template": {"spec": {"containers": [{"name": "app", "image": "demo"}]}}
                        },
                        "status": {
                            "desiredNumberScheduled": 2,
                            "numberReady": 1,
                            "updatedNumberScheduled": 1,
                        },
                    },
                ]
            }

    result = await rancher_daemonsets_list(
        namespace="kube-system",
        cluster_id="venue-local",
        ready=False,
        instance="work",
        settings=build_settings(),
        client=MixedDaemonSetClient(),
    )

    assert result.daemonset_count == 1
    assert [daemonset.name for daemonset in result.daemonsets] == ["not-ready-daemonset"]


@pytest.mark.asyncio
async def test_rancher_daemonset_get_returns_typed_detail() -> None:
    """Curated daemonset detail should expose template and generation detail."""

    result = await rancher_daemonset_get(
        namespace="kube-system",
        daemonset_name="kindnet",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.id == "kube-system/kindnet"
    assert result.service_account_name == "kindnet"
    assert result.containers[0].image == "docker.io/kindest/kindnetd:v20240202-8f1494ea"
