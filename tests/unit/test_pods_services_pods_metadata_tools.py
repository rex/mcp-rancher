"""Curated pod metadata tool tests (set_labels + set_annotations)."""

import pytest
from _pods_services_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.pods_services import rancher_pod_set_annotations, rancher_pod_set_labels

# rancher_pod_set_labels
# =====================================================================


class StubPodSetLabelsClient:
    """Patch-capable Steve stub for the pod set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the pod
    payload back with the supplied labels applied.
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
        """Capture the merge-patch and echo a Steve-shaped pod response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/pods/demo/demo-pod"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "id": "demo/demo-pod",
                "metadata": {
                    "name": "demo-pod",
                    "namespace": "demo",
                    "labels": new_labels,
                },
                "spec": {"nodeName": "demo-node"},
                "status": {
                    "phase": "Running",
                    "podIP": "10.244.0.10",
                    "conditions": [{"type": "Ready", "status": "True"}],
                    "containerStatuses": [
                        {
                            "name": "demo-container",
                            "image": "nginx:latest",
                            "ready": True,
                            "restartCount": 0,
                            "state": {"running": {}},
                        }
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_pod_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubPodSetLabelsClient()

    result = await rancher_pod_set_labels(
        namespace="demo",
        pod_name="demo-pod",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == "/pods/demo/demo-pod"
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-pod"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_pod_set_labels_emits_audit() -> None:
    """Audit record must carry operation='pod_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_pod_set_labels(
            namespace="demo",
            pod_name="demo-pod",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPodSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_pod_set_labels"
    assert record["operation"] == "pod_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


class StubPodSetAnnotationsClient:
    """Patch-capable Steve stub for the pod set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the pod
    payload back with the supplied annotations applied.
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
        """Capture the merge-patch and echo a Steve-shaped pod response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/pods/demo/demo-pod"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "id": "demo/demo-pod",
                "metadata": {
                    "name": "demo-pod",
                    "namespace": "demo",
                    "annotations": new_annotations,
                },
                "spec": {"nodeName": "demo-node"},
                "status": {
                    "phase": "Running",
                    "podIP": "10.244.0.10",
                    "conditions": [{"type": "Ready", "status": "True"}],
                    "containerStatuses": [
                        {
                            "name": "demo-container",
                            "image": "nginx:latest",
                            "ready": True,
                            "restartCount": 0,
                            "state": {"running": {}},
                        }
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_pod_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubPodSetAnnotationsClient()

    result = await rancher_pod_set_annotations(
        namespace="demo",
        pod_name="demo-pod",
        annotations={"prometheus.io/scrape": "true", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == "/pods/demo/demo-pod"
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_annotations = {"prometheus.io/scrape": "true", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-pod"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_pod_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='pod_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_pod_set_annotations(
            namespace="demo",
            pod_name="demo-pod",
            annotations={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPodSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_pod_set_annotations"
    assert record["operation"] == "pod_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
