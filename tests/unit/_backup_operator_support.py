# ruff: noqa: S105
"""Shared setup for the curated Backup Operator tool test suites.

Extracted from ``test_backup_operator_tools.py`` when it was split by
resource to stay under the architecture line limit. ``build_settings``,
the read-path payload constants, and the shared read stub
``StubBackupOperatorClient`` are consumed by multiple backup_operator
test modules; operation-specific stubs stay with the tests that use them.

The S105 noqa suppresses bandit's hardcoded-password rule for the test
fixtures' ``encryption-config`` secret-name string literal, which is just
a non-secret K8s resource name.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


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
