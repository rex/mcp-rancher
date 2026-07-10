"""Curated HPA metadata-setter tool tests (set_labels, set_annotations)."""

from __future__ import annotations

import pytest
from _governance_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.governance import (
    rancher_horizontal_pod_autoscaler_set_annotations,
    rancher_horizontal_pod_autoscaler_set_labels,
)


class StubHpaSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the HPA set_labels tests.

    Captures the most recent ``patch_json`` request so tests can assert on
    the merge-patch body and path, then echoes the HPA payload back with the
    supplied labels applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_labels tests don't need GET; raise to surface accidental usage."""

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
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-hpa",
                    "namespace": "demo",
                    "labels": new_labels,
                    "annotations": {"app": "demo"},
                },
                "spec": {
                    "scaleTargetRef": {"kind": "Deployment", "name": "demo-app"},
                    "minReplicas": 2,
                    "maxReplicas": 10,
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
async def test_rancher_horizontal_pod_autoscaler_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubHpaSetLabelsClient()

    result = await rancher_horizontal_pod_autoscaler_set_labels(
        namespace="demo",
        hpa_name="demo-hpa",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/autoscaling/v2/namespaces/demo/horizontalpodautoscalers/demo-hpa"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-hpa"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_set_labels_emits_audit() -> None:
    """Audit record must carry operation='hpa_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_horizontal_pod_autoscaler_set_labels(
            namespace="demo",
            hpa_name="demo-hpa",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubHpaSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_horizontal_pod_autoscaler_set_labels"
    assert record["operation"] == "hpa_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


class StubHpaSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the HPA set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can assert on
    the merge-patch body and path, then echoes the HPA payload back with the
    supplied annotations applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_annotations tests don't need GET; raise to surface accidental usage."""

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
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-hpa",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {
                    "scaleTargetRef": {"kind": "Deployment", "name": "demo-app"},
                    "minReplicas": 2,
                    "maxReplicas": 10,
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
async def test_rancher_horizontal_pod_autoscaler_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubHpaSetAnnotationsClient()

    result = await rancher_horizontal_pod_autoscaler_set_annotations(
        namespace="demo",
        hpa_name="demo-hpa",
        annotations={"owner": "platform", "tier": "production"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/autoscaling/v2/namespaces/demo/horizontalpodautoscalers/demo-hpa"
    )
    # Body is exactly the narrow patch — annotations nested under target_path=metadata.
    expected_annotations = {"owner": "platform", "tier": "production"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-hpa"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='hpa_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_horizontal_pod_autoscaler_set_annotations(
            namespace="demo",
            hpa_name="demo-hpa",
            annotations={"env": "staging"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubHpaSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_horizontal_pod_autoscaler_set_annotations"
    assert record["operation"] == "hpa_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
