"""Shared setup for the curated Longhorn tool test suites.

Extracted from ``test_longhorn_tools.py`` when it was split by resource
to stay under the architecture line limit. ``build_settings``, the
shared read stub ``StubLonghornClient``, and the resource payload
constants are consumed by the Volume/Node/Backup/Snapshot list/get test
modules; operation-specific patch stubs stay with the tests that use
them.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


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
