"""Curated Deployment tool tests (list/get + set_annotations)."""

from __future__ import annotations

import pytest
from _workloads_support import (
    StubRawK8sClient,
    build_settings,
)
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.workloads import (
    rancher_deployment_get,
    rancher_deployment_set_annotations,
    rancher_deployments_list,
)


@pytest.mark.asyncio
async def test_rancher_deployments_list_returns_typed_summaries() -> None:
    """Curated deployment list should expose rollout-aware summaries."""

    result = await rancher_deployments_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        ready=True,
        limit=5,
        label_selector="app=cattle-cluster-agent",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.cluster_id == "venue-local"
    assert result.namespace == "cattle-system"
    assert result.deployment_count == 1
    assert result.applied_query_params == {"limit": 5, "labelSelector": "app=cattle-cluster-agent"}
    assert result.deployments[0].ready is True
    assert result.deployments[0].rollout_complete is True


@pytest.mark.asyncio
async def test_rancher_deployment_get_returns_typed_detail() -> None:
    """Curated deployment detail should expose revision and condition detail."""

    result = await rancher_deployment_get(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.id == "cattle-system/cattle-cluster-agent"
    assert result.revision == "3"
    assert result.service_account_name == "cattle"
    assert result.conditions[0].type == "Available"


@pytest.mark.asyncio
async def test_rancher_deployments_list_handles_empty_collection() -> None:
    """Curated deployment list should handle an empty raw Kubernetes collection cleanly."""

    class EmptyDeploymentClient:
        """Return an empty deployment collection."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic empty collection."""

            assert (
                path
                == "/k8s/clusters/venue-local/apis/apps/v1/namespaces/cattle-system/deployments"
            )
            assert params is None
            return {"items": []}

    result = await rancher_deployments_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=EmptyDeploymentClient(),
    )

    assert result.deployment_count == 0
    assert result.applied_query_params == {}
    assert result.deployments == []


@pytest.mark.asyncio
async def test_rancher_deployments_list_filters_ready_items() -> None:
    """Curated deployment list should filter by computed rollout readiness."""

    class MixedDeploymentClient:
        """Deterministic workload client with ready and non-ready deployments."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return mixed deployment payloads."""

            assert (
                path
                == "/k8s/clusters/venue-local/apis/apps/v1/namespaces/cattle-system/deployments"
            )
            assert params is None
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "ready-deployment",
                            "namespace": "cattle-system",
                            "generation": 2,
                        },
                        "spec": {
                            "replicas": 1,
                            "selector": {"matchLabels": {"app": "ready"}},
                            "template": {
                                "spec": {"containers": [{"name": "app", "image": "demo"}]}
                            },
                        },
                        "status": {
                            "observedGeneration": 2,
                            "readyReplicas": 1,
                            "availableReplicas": 1,
                            "updatedReplicas": 1,
                        },
                    },
                    {
                        "metadata": {
                            "name": "not-ready-deployment",
                            "namespace": "cattle-system",
                            "generation": 2,
                        },
                        "spec": {
                            "replicas": 2,
                            "selector": {"matchLabels": {"app": "not-ready"}},
                            "template": {
                                "spec": {"containers": [{"name": "app", "image": "demo"}]}
                            },
                        },
                        "status": {
                            "observedGeneration": 2,
                            "readyReplicas": 1,
                            "availableReplicas": 1,
                            "updatedReplicas": 1,
                        },
                    },
                ]
            }

    result = await rancher_deployments_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        ready=True,
        instance="work",
        settings=build_settings(),
        client=MixedDeploymentClient(),
    )

    assert result.deployment_count == 1
    assert [deployment.name for deployment in result.deployments] == ["ready-deployment"]


# rancher_deployment_set_annotations (3-patch coexistence proof)
# =====================================================================
#
# This test class proves that a THIRD patch (set_annotations) can coexist
# alongside scale + set_labels on the same deployments descriptor. It is
# the strongest test of the multi-patch substrate to date.


class StubDeploymentSetAnnotationsClient:
    """Patch-capable stub for the deployment set_annotations tests.

    Captures the most recent patch_json request so tests can assert
    on the merge-patch body.
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

        detail = (
            "/k8s/clusters/venue-local/apis/apps/v1/namespaces/"
            "cattle-system/deployments/cattle-cluster-agent"
        )
        if path == detail:
            assert params is None
            metadata_patch = payload.get("metadata")
            assert isinstance(metadata_patch, dict)
            new_annotations = metadata_patch.get("annotations") or {}
            return {
                "metadata": {
                    "name": "cattle-cluster-agent",
                    "namespace": "cattle-system",
                    "annotations": new_annotations,
                    "labels": {},
                    "generation": 5,
                },
                "spec": {
                    "replicas": 2,
                    "selector": {"matchLabels": {"app": "cattle-cluster-agent"}},
                    "template": {
                        "spec": {
                            "serviceAccountName": "cattle",
                            "containers": [
                                {
                                    "name": "cluster-register",
                                    "image": "rancher/rancher-agent:v2.6.5",
                                }
                            ],
                        }
                    },
                },
                "status": {
                    "observedGeneration": 4,
                    "readyReplicas": 2,
                    "availableReplicas": 2,
                    "updatedReplicas": 2,
                },
            }
        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_deployment_set_annotations_uses_metadata_target_path() -> None:
    """Set_annotations lands at the resource detail path with body
    {metadata: {annotations: <map>}} — distinct from scale's
    {spec: {replicas: N}} and set_labels' {metadata: {labels: <map>}}.
    Proves all three patches coexist on one descriptor and target
    independent subtrees.
    """

    reset_rate_limit_state()
    client = StubDeploymentSetAnnotationsClient()

    result = await rancher_deployment_set_annotations(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        annotations={"app.kubernetes.io/managed-by": "helm", "version": "1.0"},
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/"
        "cattle-system/deployments/cattle-cluster-agent"
    )
    assert client.last_patch_payload == {
        "metadata": {"annotations": {"app.kubernetes.io/managed-by": "helm", "version": "1.0"}}
    }
    assert result.id == "cattle-system/cattle-cluster-agent"


@pytest.mark.asyncio
async def test_rancher_deployment_set_annotations_emits_audit_with_set_annotations_op() -> None:
    """Audit operation = deployment_set_annotations (not deployment_scale or
    deployment_set_labels). The 3-patch substrate's defining audit test:
    all three patches on one descriptor emit distinct operation names.
    """

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_deployment_set_annotations(
            namespace="cattle-system",
            deployment_name="cattle-cluster-agent",
            annotations={"env": "prod"},
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubDeploymentSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_deployment_set_annotations"
    assert record["operation"] == "deployment_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
