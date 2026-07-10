"""Curated disruption-management read tool tests (list/get)."""

from __future__ import annotations

import pytest
from _disruption_support import StubRawK8sClient, build_settings

from rancher_mcp.tools.disruption import (
    rancher_pod_disruption_budget_get,
    rancher_pod_disruption_budgets_list,
)


@pytest.mark.asyncio
async def test_rancher_pod_disruption_budgets_list_returns_typed_summaries() -> None:
    """Curated PDB list should expose typed disruption summaries."""

    result = await rancher_pod_disruption_budgets_list(
        namespace="storage-validation",
        cluster_id="venue-local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.cluster_id == "venue-local"
    assert result.namespace == "storage-validation"
    assert result.budget_count == 1
    assert result.pod_disruption_budgets[0].id == "storage-validation/demo-consumer-pdb"
    assert result.pod_disruption_budgets[0].min_available == "1"
    assert result.pod_disruption_budgets[0].disruption_allowed is False


@pytest.mark.asyncio
async def test_rancher_pod_disruption_budget_get_returns_typed_detail() -> None:
    """Curated PDB detail should expose selector and condition detail."""

    result = await rancher_pod_disruption_budget_get(
        namespace="storage-validation",
        budget_name="demo-consumer-pdb",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.id == "storage-validation/demo-consumer-pdb"
    assert result.min_available == "1"
    assert result.selector_match_labels == {"app": "demo-consumer"}
    assert result.conditions[0].reason == "InsufficientPods"
