"""Curated Longhorn Volume tool tests (list/get)."""

from __future__ import annotations

import pytest
from _longhorn_support import (
    _VOLUME_PAYLOAD,
    StubLonghornClient,
    build_settings,
)

from rancher_mcp.tools.longhorn import (
    rancher_longhorn_volume_get,
    rancher_longhorn_volumes_list,
)


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
