"""Curated Longhorn tool tests (Volume, Node, Backup, Snapshot)."""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.longhorn import (
    rancher_longhorn_backup_get,
    rancher_longhorn_backups_list,
    rancher_longhorn_node_get,
    rancher_longhorn_nodes_list,
    rancher_longhorn_snapshot_get,
    rancher_longhorn_snapshots_list,
    rancher_longhorn_volume_get,
    rancher_longhorn_volume_set_annotations,
    rancher_longhorn_volume_set_labels,
    rancher_longhorn_volumes_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for Longhorn tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_VOLUME_PAYLOAD = {
    "metadata": {
        "name": "pvc-demo",
        "namespace": "longhorn-system",
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

_NODE_PAYLOAD = {
    "metadata": {
        "name": "worker-1",
        "namespace": "longhorn-system",
        "annotations": {"team": "storage"},
    },
    "spec": {
        "allowScheduling": True,
        "evictionRequested": False,
        "tags": ["ssd", "fast"],
    },
    "status": {
        "conditions": [
            {"type": "Ready", "status": "True"},
            {"type": "Schedulable", "status": "True"},
        ],
        "diskStatus": {
            "disk-1": {"storageAvailable": 100, "storageMaximum": 200},
            "disk-2": {"storageAvailable": 50, "storageMaximum": 150},
        },
    },
}

_BACKUP_PAYLOAD = {
    "metadata": {
        "name": "backup-abc",
        "namespace": "longhorn-system",
        "annotations": {},
    },
    "spec": {
        "snapshotName": "snap-001",
    },
    "status": {
        "state": "Ready",
        "volumeName": "pvc-demo",
        "size": "5368709120",
        "error": "",
        "backupCreatedAt": "2026-05-01T00:00:00Z",
        "lastSyncedAt": "2026-05-01T00:00:01Z",
        "url": "s3://longhorn-backups/pvc-demo/backup-abc",
    },
}

_SNAPSHOT_PAYLOAD = {
    "metadata": {
        "name": "snap-001",
        "namespace": "longhorn-system",
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


class StubLonghornClient:
    """Deterministic raw Kubernetes proxy client for Longhorn tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake Longhorn CRD payloads."""

        ns_root = "/k8s/clusters/local/apis/longhorn.io/v1beta2/namespaces/longhorn-system"

        if path == f"{ns_root}/volumes":
            assert params == {"limit": 5}
            return {"items": [_VOLUME_PAYLOAD]}
        if path == f"{ns_root}/volumes/pvc-demo":
            assert params is None
            return _VOLUME_PAYLOAD

        if path == f"{ns_root}/nodes":
            assert params == {"limit": 5}
            return {"items": [_NODE_PAYLOAD]}
        if path == f"{ns_root}/nodes/worker-1":
            assert params is None
            return _NODE_PAYLOAD

        if path == f"{ns_root}/backups":
            assert params == {"limit": 5}
            return {"items": [_BACKUP_PAYLOAD]}
        if path == f"{ns_root}/backups/backup-abc":
            assert params is None
            return _BACKUP_PAYLOAD

        if path == f"{ns_root}/snapshots":
            assert params == {"limit": 5}
            return {"items": [_SNAPSHOT_PAYLOAD]}
        if path == f"{ns_root}/snapshots/snap-001":
            assert params is None
            return _SNAPSHOT_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")


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


@pytest.mark.asyncio
async def test_rancher_longhorn_nodes_list_derives_ready_and_schedulable() -> None:
    """List should derive ready/schedulable booleans from status.conditions."""

    result = await rancher_longhorn_nodes_list(
        namespace="longhorn-system",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubLonghornClient(),
    )

    assert result.node_count == 1
    [node] = result.nodes
    assert node.name == "worker-1"
    assert node.allow_scheduling is True
    assert node.eviction_requested is False
    assert node.tags == ["ssd", "fast"]
    assert node.ready is True
    assert node.schedulable is True
    assert node.disk_count == 2


@pytest.mark.asyncio
async def test_rancher_longhorn_node_get_aggregates_disk_storage() -> None:
    """Detail should sum storageAvailable / storageMaximum across all disks."""

    result = await rancher_longhorn_node_get(
        namespace="longhorn-system",
        node_name="worker-1",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubLonghornClient(),
    )

    assert result.name == "worker-1"
    # disk-1: 100/200, disk-2: 50/150 → totals 150/350
    assert result.storage_available_total == 150
    assert result.storage_maximum_total == 350
    assert result.disk_count == 2


@pytest.mark.asyncio
async def test_rancher_longhorn_backups_list_returns_summary() -> None:
    """List should expose state, volume name, snapshot name, size."""

    result = await rancher_longhorn_backups_list(
        namespace="longhorn-system",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubLonghornClient(),
    )

    assert result.backup_count == 1
    [backup] = result.backups
    assert backup.name == "backup-abc"
    assert backup.state == "Ready"
    assert backup.volume_name == "pvc-demo"
    assert backup.snapshot_name == "snap-001"
    assert backup.size == "5368709120"


@pytest.mark.asyncio
async def test_rancher_longhorn_backup_get_returns_url_and_timestamps() -> None:
    """Detail should expose backup URL and timestamps."""

    result = await rancher_longhorn_backup_get(
        namespace="longhorn-system",
        backup_name="backup-abc",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubLonghornClient(),
    )

    assert result.name == "backup-abc"
    assert result.url == "s3://longhorn-backups/pvc-demo/backup-abc"
    assert result.backup_created_at == "2026-05-01T00:00:00Z"
    assert result.last_synced_at == "2026-05-01T00:00:01Z"


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
