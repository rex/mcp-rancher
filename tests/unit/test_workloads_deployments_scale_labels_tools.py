"""Curated Deployment tool tests (scale + set_labels, incl. multi-patch coexistence)."""

from __future__ import annotations

import pytest
from _workloads_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.workloads import (
    rancher_deployment_scale,
    rancher_deployment_set_labels,
)

# =====================================================================
# rancher_deployment_scale (PatchConfig substrate end-to-end)
# =====================================================================


class StubScaleClient:
    """Patch-capable raw Kubernetes proxy stub for the scale tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body, then echoes the deployment
    payload back with the new replica count applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The scale tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Kubernetes-shaped response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail = (
            "/k8s/clusters/venue-local/apis/apps/v1/namespaces/"
            "cattle-system/deployments/cattle-cluster-agent"
        )
        if path == detail:
            assert params is None
            spec = payload.get("spec")
            assert isinstance(spec, dict)
            new_replicas = spec.get("replicas")
            return {
                "metadata": {
                    "name": "cattle-cluster-agent",
                    "namespace": "cattle-system",
                    "annotations": {
                        "deployment.kubernetes.io/revision": "4",
                    },
                    "generation": 5,
                },
                "spec": {
                    "replicas": new_replicas,
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
                    "readyReplicas": new_replicas if isinstance(new_replicas, int) else 0,
                    "availableReplicas": new_replicas if isinstance(new_replicas, int) else 0,
                    "updatedReplicas": new_replicas if isinstance(new_replicas, int) else 0,
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_deployment_scale_sends_merge_patch_at_spec_subtree() -> None:
    """Scale must PATCH the detail path with the args nested under target_path.

    For PatchConfig.target_path='spec' and a `replicas` arg, the body
    must be {"spec": {"replicas": N}} — NOT a top-level {"replicas": N}
    and NOT a full deployment payload (that'd be apply, not patch).
    """

    reset_rate_limit_state()
    client = StubScaleClient()

    result = await rancher_deployment_scale(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        replicas=5,
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/"
        "cattle-system/deployments/cattle-cluster-agent"
    )
    # Body is exactly the narrow patch — only the changed subtree.
    assert client.last_patch_payload == {"spec": {"replicas": 5}}

    # Response is shaped through get's pipeline — same curated detail.
    assert result.id == "cattle-system/cattle-cluster-agent"
    # The echoed response carries the new replica count.
    assert result.payload is not None
    spec = result.payload.get("spec")
    assert isinstance(spec, dict)
    assert spec["replicas"] == 5


@pytest.mark.asyncio
async def test_rancher_deployment_scale_emits_audit_with_scale_op() -> None:
    """Scale audit records carry operation=deployment_scale (not _patch)."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_deployment_scale(
            namespace="cattle-system",
            deployment_name="cattle-cluster-agent",
            replicas=3,
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubScaleClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_deployment_scale"
    assert record["operation"] == "deployment_scale"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    # Audit captures arg names but never values — replicas count must
    # not appear in the record string representation.
    assert "3" not in str(record.get("arg_keys", []))
    assert "replicas" in record["arg_keys"]


# =====================================================================
# rancher_deployment_set_labels (multi-patch substrate proof)
# =====================================================================
#
# This test class exists alongside StubScaleClient. It proves a single
# descriptor can carry MULTIPLE narrow patches (scale + set_labels) on
# the same resource — the J-3-extension-multi-patch substrate evolution.


class StubDeploymentSetLabelsClient:
    """Patch-capable stub for the deployment set_labels tests.

    Captures the most recent patch_json request so tests can assert
    on the merge-patch body. The stub answers ONLY on the deployment
    detail path used by the test fixture — any other path is an
    AssertionError.
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
            new_labels = metadata_patch.get("labels") or {}
            return {
                "metadata": {
                    "name": "cattle-cluster-agent",
                    "namespace": "cattle-system",
                    "annotations": {
                        "deployment.kubernetes.io/revision": "3",
                    },
                    "labels": new_labels,
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
async def test_rancher_deployment_set_labels_uses_metadata_target_path() -> None:
    """Set_labels lands at the resource detail path with body
    {metadata: {labels: <map>}} — distinct from scale's
    {spec: {replicas: N}} body. Proves both patches coexist on
    one descriptor and target different subtrees.
    """

    reset_rate_limit_state()
    client = StubDeploymentSetLabelsClient()

    result = await rancher_deployment_set_labels(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        labels={"app": "cattle", "tier": "agent"},
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/"
        "cattle-system/deployments/cattle-cluster-agent"
    )
    assert client.last_patch_payload == {"metadata": {"labels": {"app": "cattle", "tier": "agent"}}}

    assert result.id == "cattle-system/cattle-cluster-agent"


@pytest.mark.asyncio
async def test_rancher_deployment_set_labels_emits_audit_with_set_labels_op() -> None:
    """Audit operation = deployment_set_labels (not deployment_scale).

    This is the multi-patch substrate's defining test: two patches on
    one descriptor must emit DIFFERENT operation names so audit
    records correctly attribute work to the called tool.
    """

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_deployment_set_labels(
            namespace="cattle-system",
            deployment_name="cattle-cluster-agent",
            labels={"app": "demo"},
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubDeploymentSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_deployment_set_labels"
    assert record["operation"] == "deployment_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


@pytest.mark.asyncio
async def test_deployment_scale_and_set_labels_coexist_on_same_descriptor() -> None:
    """Smoke check: both patch tools exist on the deployments
    descriptor and target different subtrees independently.
    """

    reset_rate_limit_state()
    scale_client = StubScaleClient()
    labels_client = StubDeploymentSetLabelsClient()

    # Scale targets spec.replicas
    await rancher_deployment_scale(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        replicas=4,
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=scale_client,
    )
    assert scale_client.last_patch_payload == {"spec": {"replicas": 4}}

    # set_labels targets metadata.labels — fully independent body shape.
    reset_rate_limit_state()
    await rancher_deployment_set_labels(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        labels={"role": "edge"},
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=labels_client,
    )
    assert labels_client.last_patch_payload == {"metadata": {"labels": {"role": "edge"}}}
