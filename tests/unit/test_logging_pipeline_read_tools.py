"""Curated logging-pipeline read tool tests (list + get)."""

from __future__ import annotations

import pytest
from _logging_pipeline_support import (
    _CLUSTER_FLOW_PAYLOAD,
    _CLUSTER_OUTPUT_PAYLOAD,
    _FLOW_PAYLOAD,
    _OUTPUT_PAYLOAD,
    StubLoggingPipelineClient,
    build_settings,
)

from rancher_mcp.tools.logging_pipeline import (
    rancher_cluster_flow_get,
    rancher_cluster_flows_list,
    rancher_cluster_output_get,
    rancher_cluster_outputs_list,
    rancher_flow_get,
    rancher_flows_list,
    rancher_output_get,
    rancher_outputs_list,
)


@pytest.mark.asyncio
async def test_rancher_outputs_list_detects_output_type() -> None:
    """List should auto-detect output_type from the first non-loggingRef key."""

    result = await rancher_outputs_list(
        namespace="logging",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.output_count == 1
    [out] = result.outputs
    assert out.name == "s3-out"
    assert out.output_type == "s3"
    assert out.logging_ref == "default"


@pytest.mark.asyncio
async def test_rancher_output_get_returns_detail() -> None:
    """Detail should expose output_type, annotation_keys, full payload."""

    result = await rancher_output_get(
        namespace="logging",
        output_name="s3-out",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.name == "s3-out"
    assert result.output_type == "s3"
    assert result.annotation_keys == ["app"]
    assert result.payload == _OUTPUT_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_cluster_outputs_list_returns_summary() -> None:
    """ClusterOutput list should detect type without requiring namespace path."""

    result = await rancher_cluster_outputs_list(
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.cluster_output_count == 1
    [cout] = result.cluster_outputs
    assert cout.name == "loki-cout"
    assert cout.output_type == "loki"


@pytest.mark.asyncio
async def test_rancher_cluster_output_get_returns_detail() -> None:
    """ClusterOutput detail should expose output_type and full payload."""

    result = await rancher_cluster_output_get(
        cluster_output_name="loki-cout",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.name == "loki-cout"
    assert result.output_type == "loki"
    assert result.payload == _CLUSTER_OUTPUT_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_flows_list_counts_match_and_filter() -> None:
    """Flow list should count match clauses and filters, expose output refs."""

    result = await rancher_flows_list(
        namespace="logging",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.flow_count == 1
    [flow] = result.flows
    assert flow.name == "app-flow"
    assert flow.match_count == 2
    assert flow.filter_count == 1
    assert flow.local_output_refs == ["s3-out"]
    assert flow.global_output_refs == ["loki-cout"]


@pytest.mark.asyncio
async def test_rancher_flow_get_returns_detail() -> None:
    """Flow detail should include payload + match/filter counts."""

    result = await rancher_flow_get(
        namespace="logging",
        flow_name="app-flow",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.name == "app-flow"
    assert result.match_count == 2
    assert result.filter_count == 1
    assert result.annotation_keys == ["team"]
    assert result.payload == _FLOW_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_cluster_flows_list_returns_summary() -> None:
    """ClusterFlow list should expose match/filter counts and global output refs."""

    result = await rancher_cluster_flows_list(
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.cluster_flow_count == 1
    [cflow] = result.cluster_flows
    assert cflow.name == "system-cflow"
    assert cflow.match_count == 1
    assert cflow.filter_count == 0
    assert cflow.global_output_refs == ["loki-cout"]


@pytest.mark.asyncio
async def test_rancher_cluster_flow_get_returns_detail() -> None:
    """ClusterFlow detail should include payload."""

    result = await rancher_cluster_flow_get(
        cluster_flow_name="system-cflow",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.name == "system-cflow"
    assert result.match_count == 1
    assert result.payload == _CLUSTER_FLOW_PAYLOAD
