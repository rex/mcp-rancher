"""Curated Longhorn Volume tool tests (list/get + set_labels/set_annotations)."""

from __future__ import annotations

import pytest
from _longhorn_support import (
    _VOLUME_PAYLOAD,
    StubLonghornClient,
    build_settings,
)
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.longhorn import (
    rancher_longhorn_volume_get,
    rancher_longhorn_volume_set_annotations,
    rancher_longhorn_volume_set_labels,
    rancher_longhorn_volumes_list,
)


@pytest.mark.asyncio
async def test_rancher_longhorn_volumes_list_returns_summary() -> None:
    """List should expose state, robustness, replicas, and current node."""

    result = await rancher_longhorn_volumes_list(
        namespace="longhorn-system",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubLonghornClient(),
    )

    assert result.volume_count == 1
    [vol] = result.volumes
    assert vol.name == "pvc-demo"
    assert vol.state == "attached"
    assert vol.robustness == "healthy"
    assert vol.number_of_replicas == 3
    assert vol.access_mode == "rwo"
    assert vol.current_node_id == "worker-1"


@pytest.mark.asyncio
async def test_rancher_longhorn_volume_get_returns_detail() -> None:
    """Detail should expose engine image, actual size, and full payload."""

    result = await rancher_longhorn_volume_get(
        namespace="longhorn-system",
        volume_name="pvc-demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubLonghornClient(),
    )

    assert result.name == "pvc-demo"
    assert result.current_image == "longhornio/longhorn-engine:v1.5.0"
    assert result.actual_size == "5368709120"
    assert result.restore_required is False
    assert result.payload == _VOLUME_PAYLOAD


# rancher_longhorn_volume_set_labels (PatchConfig substrate — metadata target)
# ============================================================================


class StubLonghornVolumeSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the volume
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
        """Capture the merge-patch and echo a Kubernetes-shaped volume response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/longhorn.io/v1beta2"
            "/namespaces/longhorn-system/volumes/pvc-demo"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "pvc-demo",
                    "namespace": "longhorn-system",
                    "labels": new_labels,
                    "annotations": {"longhorn.io/source": "manual"},
                },
                "spec": {
                    "size": "10737418240",
                    "numberOfReplicas": 3,
                    "accessMode": "rwo",
                    "frontend": "blockdev",
                },
                "status": {
                    "state": "attached",
                    "robustness": "healthy",
                    "currentNodeID": "worker-1",
                    "currentImage": "longhornio/longhorn-engine:v1.5.0",
                    "actualSize": "5368709120",
                    "restoreRequired": False,
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_longhorn_volume_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubLonghornVolumeSetLabelsClient()

    result = await rancher_longhorn_volume_set_labels(
        namespace="longhorn-system",
        volume_name="pvc-demo",
        labels={"env": "prod", "team": "storage"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/longhorn.io/v1beta2/namespaces/longhorn-system/volumes/pvc-demo"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "storage"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "pvc-demo"
    assert result.namespace == "longhorn-system"


@pytest.mark.asyncio
async def test_rancher_longhorn_volume_set_labels_emits_audit() -> None:
    """Audit record must carry operation='longhorn_volume_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_longhorn_volume_set_labels(
            namespace="longhorn-system",
            volume_name="pvc-demo",
            labels={"app": "storage"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubLonghornVolumeSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_longhorn_volume_set_labels"
    assert record["operation"] == "longhorn_volume_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_longhorn_volume_set_annotations (PatchConfig substrate — metadata target)
# ===================================================================================


class StubLonghornVolumeSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the volume
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
        """Capture the merge-patch and echo a Kubernetes-shaped volume response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/longhorn.io/v1beta2"
            "/namespaces/longhorn-system/volumes/pvc-demo"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "pvc-demo",
                    "namespace": "longhorn-system",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {
                    "size": "10737418240",
                    "numberOfReplicas": 3,
                    "accessMode": "rwo",
                    "frontend": "blockdev",
                },
                "status": {
                    "state": "attached",
                    "robustness": "healthy",
                    "currentNodeID": "worker-1",
                    "currentImage": "longhornio/longhorn-engine:v1.5.0",
                    "actualSize": "5368709120",
                    "restoreRequired": False,
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_longhorn_volume_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubLonghornVolumeSetAnnotationsClient()

    result = await rancher_longhorn_volume_set_annotations(
        namespace="longhorn-system",
        volume_name="pvc-demo",
        annotations={"owner": "team-storage", "env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/longhorn.io/v1beta2/namespaces/longhorn-system/volumes/pvc-demo"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_annotations = {"owner": "team-storage", "env": "prod"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "pvc-demo"
    assert result.namespace == "longhorn-system"


@pytest.mark.asyncio
async def test_rancher_longhorn_volume_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='longhorn_volume_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_longhorn_volume_set_annotations(
            namespace="longhorn-system",
            volume_name="pvc-demo",
            annotations={"app": "storage"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubLonghornVolumeSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_longhorn_volume_set_annotations"
    assert record["operation"] == "longhorn_volume_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
