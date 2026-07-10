"""Curated ReplicaSet tool tests (list/get)."""

from __future__ import annotations

import pytest
from _workloads_support import (
    StubRawK8sClient,
    build_settings,
)

from rancher_mcp.tools.workloads import (
    rancher_replica_set_get,
    rancher_replica_sets_list,
)


@pytest.mark.asyncio
async def test_rancher_replica_sets_list_returns_typed_summaries() -> None:
    """Curated replicaset list should expose readiness-aware summaries."""

    result = await rancher_replica_sets_list(
        namespace="apps",
        cluster_id="venue-local",
        ready=True,
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.cluster_id == "venue-local"
    assert result.namespace == "apps"
    assert result.replica_set_count == 1
    assert result.replica_sets[0].name == "nginx-rs"
    assert result.replica_sets[0].ready is True
    assert result.replica_sets[0].replicas == 3
    assert result.replica_sets[0].ready_replicas == 3


@pytest.mark.asyncio
async def test_rancher_replica_set_get_returns_typed_detail() -> None:
    """Curated replicaset detail should expose annotation keys and full payload."""

    result = await rancher_replica_set_get(
        namespace="apps",
        replica_set_name="nginx-rs",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.id == "apps/nginx-rs"
    assert result.ready is True
    assert result.annotation_keys == ["deployment.kubernetes.io/desired-replicas"]
    assert result.container_images == ["nginx:1.25"]
    assert result.payload is not None
