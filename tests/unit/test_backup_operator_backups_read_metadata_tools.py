# ruff: noqa: S105
"""Curated Backup read tests (list, get).

The S105 noqa suppresses bandit's hardcoded-password rule for the test
fixtures' ``encryption-config`` secret-name string literal, which is just
a non-secret K8s resource name.
"""

from __future__ import annotations

import pytest
from _backup_operator_support import (
    _BACKUP_PAYLOAD,
    StubBackupOperatorClient,
    build_settings,
)

from rancher_mcp.tools.backup_operator import (
    rancher_backup_get,
    rancher_backups_list,
)


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
