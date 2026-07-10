"""Curated Longhorn Snapshot tool tests (list/get + set_labels/set_annotations)."""

from __future__ import annotations

import pytest
from _longhorn_support import (
    _SNAPSHOT_PAYLOAD,
    StubLonghornClient,
    build_settings,
)
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.longhorn import (
    rancher_longhorn_snapshot_get,
    rancher_longhorn_snapshot_set_annotations,
    rancher_longhorn_snapshot_set_labels,
    rancher_longhorn_snapshots_list,
)


@pytest.mark.asyncio
async def test_rancher_longhorn_snapshots_list_returns_summary() -> None:
    """List should expose volume, creation time, size, ready_to_use."""

    result = await rancher_longhorn_snapshots_list(
        namespace="longhorn-system",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubLonghornClient(),
    )

    assert result.snapshot_count == 1
    [snap] = result.snapshots
    assert snap.name == "snap-001"
    assert snap.volume == "pvc-demo"
    assert snap.creation_time == "2026-05-01T00:00:00Z"
    assert snap.size == "1073741824"
    assert snap.ready_to_use is True


@pytest.mark.asyncio
async def test_rancher_longhorn_snapshot_get_returns_parent_children() -> None:
    """Detail should expose parent + children chain."""

    result = await rancher_longhorn_snapshot_get(
        namespace="longhorn-system",
        snapshot_name="snap-001",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubLonghornClient(),
    )

    assert result.name == "snap-001"
    assert result.parent == "snap-000"
    assert result.children == ["snap-002", "snap-003"]
    assert result.payload == _SNAPSHOT_PAYLOAD


# rancher_longhorn_snapshot_set_labels (PatchConfig substrate — metadata target)
# ================================================================================


class StubLonghornSnapshotSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the snapshot set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the snapshot
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
        """Capture the merge-patch and echo a Kubernetes-shaped snapshot response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/longhorn.io/v1beta2"
            "/namespaces/longhorn-system/snapshots/snap-001"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "snap-001",
                    "namespace": "longhorn-system",
                    "labels": new_labels,
                    "annotations": {},
                },
                "spec": {"volume": "pvc-demo"},
                "status": {
                    "creationTime": "2026-05-01T00:00:00Z",
                    "size": "1073741824",
                    "readyToUse": True,
                    "parent": "snap-000",
                    "children": ["snap-002", "snap-003"],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_longhorn_snapshot_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubLonghornSnapshotSetLabelsClient()

    result = await rancher_longhorn_snapshot_set_labels(
        namespace="longhorn-system",
        snapshot_name="snap-001",
        labels={"env": "prod", "team": "storage"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/longhorn.io/v1beta2/namespaces/longhorn-system/snapshots/snap-001"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "storage"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "snap-001"
    assert result.namespace == "longhorn-system"


@pytest.mark.asyncio
async def test_rancher_longhorn_snapshot_set_labels_emits_audit() -> None:
    """Audit record must carry operation='longhorn_snapshot_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_longhorn_snapshot_set_labels(
            namespace="longhorn-system",
            snapshot_name="snap-001",
            labels={"app": "storage"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubLonghornSnapshotSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_longhorn_snapshot_set_labels"
    assert record["operation"] == "longhorn_snapshot_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_longhorn_snapshot_set_annotations (PatchConfig substrate — metadata target)
# ================================================================


class StubLonghornSnapshotSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the snapshot set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the snapshot
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
        """Capture the merge-patch and echo a Kubernetes-shaped snapshot response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/longhorn.io/v1beta2"
            "/namespaces/longhorn-system/snapshots/snap-001"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "snap-001",
                    "namespace": "longhorn-system",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {"volume": "pvc-demo"},
                "status": {
                    "creationTime": "2026-05-01T00:00:00Z",
                    "size": "1073741824",
                    "readyToUse": True,
                    "parent": "snap-000",
                    "children": ["snap-002", "snap-003"],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_longhorn_snapshot_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubLonghornSnapshotSetAnnotationsClient()

    result = await rancher_longhorn_snapshot_set_annotations(
        namespace="longhorn-system",
        snapshot_name="snap-001",
        annotations={"owner": "team-storage", "managed-by": "rancher"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/longhorn.io/v1beta2/namespaces/longhorn-system/snapshots/snap-001"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_annotations = {"owner": "team-storage", "managed-by": "rancher"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "snap-001"
    assert result.namespace == "longhorn-system"


@pytest.mark.asyncio
async def test_rancher_longhorn_snapshot_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='longhorn_snapshot_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_longhorn_snapshot_set_annotations(
            namespace="longhorn-system",
            snapshot_name="snap-001",
            annotations={"app": "storage"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubLonghornSnapshotSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_longhorn_snapshot_set_annotations"
    assert record["operation"] == "longhorn_snapshot_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
