"""Curated StatefulSet tool tests (list/get + scale)."""

from __future__ import annotations

import pytest
from _workloads_support import (
    StubRawK8sClient,
    build_settings,
)

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.workloads import (
    rancher_statefulset_get,
    rancher_statefulset_scale,
    rancher_statefulsets_list,
)


@pytest.mark.asyncio
async def test_rancher_statefulsets_list_returns_typed_summaries() -> None:
    """Curated statefulset list should expose rollout-aware summaries."""

    result = await rancher_statefulsets_list(
        namespace="apps",
        cluster_id="venue-local",
        field_selector="metadata.name=demo-db",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.statefulset_count == 1
    assert result.statefulsets[0].name == "demo-db"
    assert result.statefulsets[0].ready is True


@pytest.mark.asyncio
async def test_rancher_statefulsets_list_handles_empty_collection() -> None:
    """Curated statefulset list should handle an empty raw Kubernetes collection cleanly."""

    class EmptyStatefulSetClient:
        """Return an empty statefulset collection."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic empty collection."""

            assert path == "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/statefulsets"
            assert params is None
            return {"items": []}

    result = await rancher_statefulsets_list(
        namespace="apps",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=EmptyStatefulSetClient(),
    )

    assert result.statefulset_count == 0
    assert result.applied_query_params == {}
    assert result.statefulsets == []


@pytest.mark.asyncio
async def test_rancher_statefulset_get_returns_typed_detail() -> None:
    """Curated statefulset detail should expose revision and container detail."""

    result = await rancher_statefulset_get(
        namespace="apps",
        statefulset_name="demo-db",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.id == "apps/demo-db"
    assert result.current_revision == "demo-db-7f9cfb6f8c"
    assert result.update_revision == "demo-db-7f9cfb6f8c"
    assert result.containers[0].name == "db"


# =====================================================================
# rancher_statefulset_scale (substrate generalization to a 2nd resource)
# =====================================================================


class StubStatefulSetScaleClient:
    """Patch-capable stub for the StatefulSet scale tests.

    Same shape as StubScaleClient but on the StatefulSet detail path.
    Proves the patch substrate is resource-agnostic — the same
    target_path: spec + replicas: int pattern works on any
    workload-controller resource.
    """

    def __init__(self) -> None:
        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail = "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/statefulsets/demo-db"
        if path == detail:
            assert params is None
            spec = payload.get("spec")
            assert isinstance(spec, dict)
            new_replicas = spec.get("replicas")
            return {
                "metadata": {"name": "demo-db", "namespace": "apps", "generation": 6},
                "spec": {
                    "replicas": new_replicas,
                    "serviceName": "demo-db",
                    "selector": {"matchLabels": {"app": "demo-db"}},
                    "template": {
                        "spec": {
                            "containers": [{"name": "db", "image": "postgres:16"}],
                        }
                    },
                },
                "status": {
                    "currentRevision": "demo-db-7f9cfb6f8c",
                    "updateRevision": "demo-db-7f9cfb6f8c",
                    "readyReplicas": new_replicas if isinstance(new_replicas, int) else 0,
                    "replicas": new_replicas if isinstance(new_replicas, int) else 0,
                },
            }
        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_statefulset_scale_uses_same_substrate_as_deployment_scale() -> None:
    """Statefulset scale should produce the identical merge-patch shape.

    This is the substrate-generalization test: the same PatchConfig
    pattern (target_path=spec, replicas: int) emits the same body
    shape regardless of which workload controller is being patched.
    """

    reset_rate_limit_state()
    client = StubStatefulSetScaleClient()

    result = await rancher_statefulset_scale(
        namespace="apps",
        statefulset_name="demo-db",
        replicas=3,
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/statefulsets/demo-db"
    )
    # Same narrow-patch body shape as deployment_scale: identical
    # substrate behavior across resource types.
    assert client.last_patch_payload == {"spec": {"replicas": 3}}

    # Compact mutation receipt (L-1), not the full detail.
    assert result.ok is True
    assert result.action == "scale"
    assert result.changed == {"replicas": 3}
