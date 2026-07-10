"""Curated governance read tool tests (HPA, ResourceQuota, LimitRange list/get)."""

from __future__ import annotations

import pytest
from _governance_support import (
    _HPA_PAYLOAD,
    _LIMIT_RANGE_PAYLOAD,
    StubGovernanceClient,
    build_settings,
)

from rancher_mcp.tools.governance import (
    rancher_horizontal_pod_autoscaler_get,
    rancher_horizontal_pod_autoscalers_list,
    rancher_limit_range_get,
    rancher_limit_ranges_list,
    rancher_resource_quota_get,
    rancher_resource_quotas_list,
)


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscalers_list_returns_summary() -> None:
    """List should expose target ref, min/max replicas, current/desired, metric_count."""

    result = await rancher_horizontal_pod_autoscalers_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubGovernanceClient(),
    )

    assert result.horizontal_pod_autoscaler_count == 1
    [hpa] = result.horizontal_pod_autoscalers
    assert hpa.name == "demo-hpa"
    assert hpa.target_kind == "Deployment"
    assert hpa.target_name == "demo-app"
    assert hpa.min_replicas == 2
    assert hpa.max_replicas == 10
    assert hpa.current_replicas == 5
    assert hpa.desired_replicas == 7
    assert hpa.metric_count == 3
    assert hpa.able_to_scale is True
    assert hpa.scaling_active is True


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_get_returns_metric_types() -> None:
    """Detail should expose sorted unique metric types from spec.metrics[]."""

    result = await rancher_horizontal_pod_autoscaler_get(
        namespace="demo",
        hpa_name="demo-hpa",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubGovernanceClient(),
    )

    assert result.name == "demo-hpa"
    assert result.metric_types == ["External", "Resource"]
    assert result.payload == _HPA_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_resource_quotas_list_counts_hard_and_used() -> None:
    """List should count hard limits and used entries from status."""

    result = await rancher_resource_quotas_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubGovernanceClient(),
    )

    assert result.resource_quota_count == 1
    [quota] = result.resource_quotas
    assert quota.name == "demo-quota"
    # status.hard has 3 keys; status.used has 3 keys
    assert quota.hard_limit_count == 3
    assert quota.used_count == 3
    assert quota.hard_limit_keys == ["cpu", "memory", "pods"]


@pytest.mark.asyncio
async def test_rancher_resource_quota_get_returns_hard_and_used_dicts() -> None:
    """Detail should expose the full status.hard and status.used dicts."""

    result = await rancher_resource_quota_get(
        namespace="demo",
        resource_quota_name="demo-quota",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubGovernanceClient(),
    )

    assert result.name == "demo-quota"
    assert result.hard == {"cpu": "10", "memory": "20Gi", "pods": "50"}
    assert result.used == {"cpu": "3", "memory": "5Gi", "pods": "12"}


@pytest.mark.asyncio
async def test_rancher_limit_ranges_list_collects_types_present() -> None:
    """List should expose limit_count and sorted unique types_present."""

    result = await rancher_limit_ranges_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubGovernanceClient(),
    )

    assert result.limit_range_count == 1
    [lr] = result.limit_ranges
    assert lr.name == "demo-limits"
    assert lr.limit_count == 3
    assert lr.types_present == ["Container", "PersistentVolumeClaim", "Pod"]


@pytest.mark.asyncio
async def test_rancher_limit_range_get_returns_payload() -> None:
    """Detail should expose annotation keys + full payload."""

    result = await rancher_limit_range_get(
        namespace="demo",
        limit_range_name="demo-limits",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubGovernanceClient(),
    )

    assert result.name == "demo-limits"
    assert result.payload == _LIMIT_RANGE_PAYLOAD
