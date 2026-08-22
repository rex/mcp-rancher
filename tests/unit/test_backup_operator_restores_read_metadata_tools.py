# ruff: noqa: S105
"""Curated Restore read tests (list, get).

The S105 noqa suppresses bandit's hardcoded-password rule for the test
fixtures' ``encryption-config`` secret-name string literal, which is just
a non-secret K8s resource name.
"""

from __future__ import annotations

import pytest
from _backup_operator_support import (
    _RESTORE_PAYLOAD,
    StubBackupOperatorClient,
    build_settings,
)

from rancher_mcp.tools.backup_operator import (
    rancher_restore_get,
    rancher_restores_list,
)


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
