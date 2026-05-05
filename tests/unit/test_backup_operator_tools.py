# ruff: noqa: S105
"""Curated Rancher Backup Operator tool tests (Backup, Restore).

The S105 noqa suppresses bandit's hardcoded-password rule for the
test fixtures' ``encryption-config`` secret-name string literal,
which is just a non-secret K8s resource name.
"""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.backup_operator import (
    rancher_backup_get,
    rancher_backups_list,
    rancher_restore_get,
    rancher_restores_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for backup_operator tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_BACKUP_PAYLOAD = {
    "metadata": {
        "name": "weekly-backup",
        "annotations": {"app": "rancher-backup"},
    },
    "spec": {
        "encryptionConfigSecretName": "encryption-config",
        "resourceSetName": "rancher-resource-set",
        "schedule": "@every 168h",
        "retentionCount": 4,
        "storageLocation": {
            "s3": {
                "bucketName": "rancher-backups",
                "region": "us-west-2",
                "endpoint": "s3.amazonaws.com",
            },
        },
    },
    "status": {
        "filename": "weekly-backup-2026-01-01.tar.gz",
        "lastBackupTs": "2026-01-01T00:00:00Z",
        "summary": "ready",
        "conditions": [
            {"type": "Ready", "status": "True"},
            {"type": "Reconciling", "status": "False"},
        ],
    },
}

_RESTORE_PAYLOAD = {
    "metadata": {
        "name": "demo-restore",
        "annotations": {},
    },
    "spec": {
        "backupFilename": "weekly-backup-2026-01-01.tar.gz",
        "encryptionConfigSecretName": "encryption-config",
        "prune": True,
        "storageLocation": {
            "default": {},
        },
    },
    "status": {
        "restoreCompletionTs": "2026-01-02T00:00:00Z",
        "summary": "ready",
        "conditions": [
            {"type": "Ready", "status": "True"},
        ],
    },
}


class StubBackupOperatorClient:
    """Deterministic raw Kubernetes proxy client for backup_operator tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake Backup Operator CRD payloads."""

        backups_root = "/k8s/clusters/local/apis/resources.cattle.io/v1/backups"
        if path == backups_root:
            assert params == {"limit": 5}
            return {"items": [_BACKUP_PAYLOAD]}
        if path == f"{backups_root}/weekly-backup":
            assert params is None
            return _BACKUP_PAYLOAD

        restores_root = "/k8s/clusters/local/apis/resources.cattle.io/v1/restores"
        if path == restores_root:
            assert params == {"limit": 5}
            return {"items": [_RESTORE_PAYLOAD]}
        if path == f"{restores_root}/demo-restore":
            assert params is None
            return _RESTORE_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")


@pytest.mark.asyncio
async def test_rancher_backups_list_summarizes_schedule_and_filename() -> None:
    """List should expose schedule, retention, and the latest backup filename."""

    result = await rancher_backups_list(
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubBackupOperatorClient(),
    )

    assert result.backup_count == 1
    [backup] = result.backups
    assert backup.name == "weekly-backup"
    assert backup.encryption_config_secret_name == "encryption-config"
    assert backup.resource_set_name == "rancher-resource-set"
    assert backup.schedule == "@every 168h"
    assert backup.retention_count == 4
    assert backup.backup_filename == "weekly-backup-2026-01-01.tar.gz"
    assert backup.last_backup_time == "2026-01-01T00:00:00Z"
    assert backup.summary_state == "ready"


@pytest.mark.asyncio
async def test_rancher_backup_get_returns_storage_and_conditions() -> None:
    """Detail should render the s3 storage location and condition_types_true."""

    result = await rancher_backup_get(
        backup_name="weekly-backup",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubBackupOperatorClient(),
    )

    assert result.name == "weekly-backup"
    assert result.storage_location_summary == "s3://rancher-backups (us-west-2)"
    assert result.condition_types_true == ["Ready"]
    assert result.annotation_keys == ["app"]
    assert result.payload == _BACKUP_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_restores_list_summarizes_target_filename() -> None:
    """Restore list should expose the source filename and prune flag."""

    result = await rancher_restores_list(
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubBackupOperatorClient(),
    )

    assert result.restore_count == 1
    [restore] = result.restores
    assert restore.name == "demo-restore"
    assert restore.backup_filename == "weekly-backup-2026-01-01.tar.gz"
    assert restore.encryption_config_secret_name == "encryption-config"
    assert restore.prune_value is True
    assert restore.restore_completion_ts == "2026-01-02T00:00:00Z"
    assert restore.summary_state == "ready"


@pytest.mark.asyncio
async def test_rancher_restore_get_renders_default_storage_location() -> None:
    """Detail should report `default` when the operator's default storage is used."""

    result = await rancher_restore_get(
        restore_name="demo-restore",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubBackupOperatorClient(),
    )

    assert result.name == "demo-restore"
    assert result.storage_location_summary == "default"
    assert result.condition_types_true == ["Ready"]
    assert result.payload == _RESTORE_PAYLOAD
