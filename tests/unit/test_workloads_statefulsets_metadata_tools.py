"""Curated StatefulSet tool tests (set_labels + set_annotations)."""

from __future__ import annotations

import pytest
from _workloads_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.workloads import (
    rancher_statefulset_set_annotations,
    rancher_statefulset_set_labels,
)

# =====================================================================
# rancher_statefulset_set_labels (multi-patch append: scale + set_labels)
# =====================================================================


class StubStatefulSetSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the statefulset set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the statefulset
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
        """Capture the merge-patch and echo a Kubernetes-shaped statefulset response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/statefulsets/demo-db"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-db",
                    "namespace": "apps",
                    "labels": new_labels,
                    "generation": 6,
                },
                "spec": {
                    "replicas": 3,
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
                    "readyReplicas": 3,
                    "replicas": 3,
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_statefulset_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubStatefulSetSetLabelsClient()

    result = await rancher_statefulset_set_labels(
        namespace="apps",
        statefulset_name="demo-db",
        labels={"env": "prod", "team": "platform"},
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/statefulsets/demo-db"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-db"
    assert result.namespace == "apps"


@pytest.mark.asyncio
async def test_rancher_statefulset_set_labels_emits_audit() -> None:
    """Audit record must carry operation='statefulset_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_statefulset_set_labels(
            namespace="apps",
            statefulset_name="demo-db",
            labels={"app": "web"},
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubStatefulSetSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_statefulset_set_labels"
    assert record["operation"] == "statefulset_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# =====================================================================
# rancher_statefulset_set_annotations (third patch entry: scale + set_labels + set_annotations)
# =====================================================================


class StubStatefulSetSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the statefulset set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the statefulset
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
        """Capture the merge-patch and echo a Kubernetes-shaped statefulset response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/statefulsets/demo-db"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-db",
                    "namespace": "apps",
                    "annotations": new_annotations,
                    "generation": 7,
                },
                "spec": {
                    "replicas": 3,
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
                    "readyReplicas": 3,
                    "replicas": 3,
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_statefulset_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubStatefulSetSetAnnotationsClient()

    result = await rancher_statefulset_set_annotations(
        namespace="apps",
        statefulset_name="demo-db",
        annotations={"team": "platform", "tier": "backend"},
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/statefulsets/demo-db"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_annotations = {"team": "platform", "tier": "backend"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-db"
    assert result.namespace == "apps"


@pytest.mark.asyncio
async def test_rancher_statefulset_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='statefulset_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_statefulset_set_annotations(
            namespace="apps",
            statefulset_name="demo-db",
            annotations={"sidecar.istio.io/inject": "false"},
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubStatefulSetSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_statefulset_set_annotations"
    assert record["operation"] == "statefulset_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
