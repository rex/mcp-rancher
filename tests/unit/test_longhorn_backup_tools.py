"""Curated Longhorn Backup tool tests (list/get + set_labels/set_annotations)."""

from __future__ import annotations

import pytest
from _longhorn_support import (
    StubLonghornClient,
    build_settings,
)
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.longhorn import (
    rancher_longhorn_backup_get,
    rancher_longhorn_backup_set_annotations,
    rancher_longhorn_backup_set_labels,
    rancher_longhorn_backups_list,
)


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


# rancher_longhorn_backup_set_labels (PatchConfig substrate — metadata target)
# ==============================================================================


class StubLonghornBackupSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the backup set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the backup
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
        """Capture the merge-patch and echo a Kubernetes-shaped backup response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/longhorn.io/v1beta2"
            "/namespaces/longhorn-system/backups/backup-abc"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "backup-abc",
                    "namespace": "longhorn-system",
                    "labels": new_labels,
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

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_longhorn_backup_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubLonghornBackupSetLabelsClient()

    result = await rancher_longhorn_backup_set_labels(
        namespace="longhorn-system",
        backup_name="backup-abc",
        labels={"env": "prod", "team": "storage"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/longhorn.io/v1beta2/namespaces/longhorn-system/backups/backup-abc"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "storage"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "backup-abc"
    assert result.namespace == "longhorn-system"


@pytest.mark.asyncio
async def test_rancher_longhorn_backup_set_labels_emits_audit() -> None:
    """Audit record must carry operation='longhorn_backup_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_longhorn_backup_set_labels(
            namespace="longhorn-system",
            backup_name="backup-abc",
            labels={"app": "storage"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubLonghornBackupSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_longhorn_backup_set_labels"
    assert record["operation"] == "longhorn_backup_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_longhorn_backup_set_annotations (PatchConfig substrate — metadata target)
# ==================================================================================


class StubLonghornBackupSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the backup set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the backup
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
        """Capture the merge-patch and echo a Kubernetes-shaped backup response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/longhorn.io/v1beta2"
            "/namespaces/longhorn-system/backups/backup-abc"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "backup-abc",
                    "namespace": "longhorn-system",
                    "labels": {},
                    "annotations": new_annotations,
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

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_longhorn_backup_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubLonghornBackupSetAnnotationsClient()

    result = await rancher_longhorn_backup_set_annotations(
        namespace="longhorn-system",
        backup_name="backup-abc",
        annotations={"team": "storage", "owner": "ops"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/longhorn.io/v1beta2/namespaces/longhorn-system/backups/backup-abc"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_annotations = {"team": "storage", "owner": "ops"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "backup-abc"
    assert result.namespace == "longhorn-system"


@pytest.mark.asyncio
async def test_rancher_longhorn_backup_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='longhorn_backup_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_longhorn_backup_set_annotations(
            namespace="longhorn-system",
            backup_name="backup-abc",
            annotations={"app": "storage"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubLonghornBackupSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_longhorn_backup_set_annotations"
    assert record["operation"] == "longhorn_backup_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
