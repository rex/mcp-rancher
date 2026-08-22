"""Curated Longhorn Backup tool tests (list/get)."""

from __future__ import annotations

import pytest
from _longhorn_support import (
    StubLonghornClient,
    build_settings,
)

from rancher_mcp.tools.longhorn import (
    rancher_longhorn_backup_get,
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
