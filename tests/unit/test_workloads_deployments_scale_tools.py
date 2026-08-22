"""Curated Deployment tool tests (scale)."""

from __future__ import annotations

import pytest
from _workloads_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.workloads import (
    rancher_deployment_scale,
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

    # Response is a compact mutation receipt (L-1), not the full detail.
    assert result.ok is True
    assert result.action == "scale"
    assert result.name == "cattle-cluster-agent"
    assert result.changed == {"replicas": 5}


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
