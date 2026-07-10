"""Curated HPA spec-setter tool tests (set_min_max)."""

from __future__ import annotations

import pytest
from _governance_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.governance import rancher_horizontal_pod_autoscaler_set_min_max


class StubHpaSetMinMaxClient:
    """Patch-capable raw Kubernetes proxy stub for the HPA set_min_max tests.

    Captures the most recent ``patch_json`` request so tests can assert on
    the merge-patch body and path, then echoes the HPA payload back with the
    supplied minReplicas and maxReplicas applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_min_max tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Kubernetes-shaped HPA response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/autoscaling/v2"
            "/namespaces/demo/horizontalpodautoscalers/demo-hpa"
        )
        if path == detail_path:
            assert params is None
            spec = payload.get("spec")
            assert isinstance(spec, dict)
            min_r = spec.get("minReplicas", 2)
            max_r = spec.get("maxReplicas", 10)
            return {
                "metadata": {
                    "name": "demo-hpa",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": {},
                },
                "spec": {
                    "scaleTargetRef": {"kind": "Deployment", "name": "demo-app"},
                    "minReplicas": min_r,
                    "maxReplicas": max_r,
                    "metrics": [
                        {"type": "Resource", "resource": {"name": "cpu"}},
                    ],
                },
                "status": {
                    "currentReplicas": 2,
                    "desiredReplicas": 2,
                    "conditions": [
                        {"type": "AbleToScale", "status": "True"},
                        {"type": "ScalingActive", "status": "True"},
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_set_min_max_round_trip() -> None:
    """PATCH body must be exactly {spec: {minReplicas: N, maxReplicas: M}} at the detail path."""

    reset_rate_limit_state()
    client = StubHpaSetMinMaxClient()

    result = await rancher_horizontal_pod_autoscaler_set_min_max(
        namespace="demo",
        hpa_name="demo-hpa",
        minReplicas=3,
        maxReplicas=15,
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/autoscaling/v2/namespaces/demo/horizontalpodautoscalers/demo-hpa"
    )
    # Body is exactly the narrow patch — camelCase keys nested under target_path=spec.
    assert client.last_patch_payload == {"spec": {"minReplicas": 3, "maxReplicas": 15}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-hpa"
    assert result.namespace == "demo"
    assert result.min_replicas == 3
    assert result.max_replicas == 15


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_set_min_max_emits_audit() -> None:
    """Audit record must carry operation='hpa_set_min_max'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_horizontal_pod_autoscaler_set_min_max(
            namespace="demo",
            hpa_name="demo-hpa",
            minReplicas=1,
            maxReplicas=5,
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubHpaSetMinMaxClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_horizontal_pod_autoscaler_set_min_max"
    assert record["operation"] == "hpa_set_min_max"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "minReplicas" in record["arg_keys"]
    assert "maxReplicas" in record["arg_keys"]
