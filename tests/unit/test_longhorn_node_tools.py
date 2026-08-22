"""Curated Longhorn Node tool tests (list/get)."""

from __future__ import annotations

import pytest
from _longhorn_support import (
    StubLonghornClient,
    build_settings,
)

from rancher_mcp.tools.longhorn import (
    rancher_longhorn_node_get,
    rancher_longhorn_nodes_list,
)


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
