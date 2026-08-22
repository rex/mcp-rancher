"""Curated Longhorn Snapshot tool tests (list/get)."""

from __future__ import annotations

import pytest
from _longhorn_support import (
    _SNAPSHOT_PAYLOAD,
    StubLonghornClient,
    build_settings,
)

from rancher_mcp.tools.longhorn import (
    rancher_longhorn_snapshot_get,
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
