"""Curated PolicyReport read tool tests (PolicyReport, ClusterPolicyReport list/get)."""

from __future__ import annotations

import pytest
from _policy_reports_support import (
    _CLUSTER_POLICY_REPORT_PAYLOAD,
    _POLICY_REPORT_PAYLOAD,
    StubPolicyReportsClient,
    build_settings,
)

from rancher_mcp.tools.policy_reports import (
    rancher_cluster_policy_report_get,
    rancher_cluster_policy_reports_list,
    rancher_policy_report_get,
    rancher_policy_reports_list,
)


@pytest.mark.asyncio
async def test_rancher_policy_reports_list_summarizes_counts() -> None:
    """List should expose pass/fail/warn/error/skip counts and result_count."""

    result = await rancher_policy_reports_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubPolicyReportsClient(),
    )

    assert result.policy_report_count == 1
    [rep] = result.policy_reports
    assert rep.name == "demo-report"
    assert rep.pass_count == 5
    assert rep.fail_count == 3
    assert rep.warn_count == 1
    assert rep.error_count == 0
    assert rep.skip_count == 2
    assert rep.result_count == 6
    # Top failing policies are sorted unique policy names with at least one fail.
    assert rep.top_failing_policies == ["disallow-latest", "require-labels"]


@pytest.mark.asyncio
async def test_rancher_policy_report_get_returns_detail_with_payload() -> None:
    """Detail should expose annotation_keys + full payload."""

    result = await rancher_policy_report_get(
        namespace="demo",
        report_name="demo-report",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubPolicyReportsClient(),
    )

    assert result.name == "demo-report"
    assert result.fail_count == 3
    assert result.top_failing_policies == ["disallow-latest", "require-labels"]
    assert result.annotation_keys == ["engine"]
    assert result.payload == _POLICY_REPORT_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_cluster_policy_reports_list_returns_summary() -> None:
    """ClusterPolicyReport list should work without a namespace path."""

    result = await rancher_cluster_policy_reports_list(
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubPolicyReportsClient(),
    )

    assert result.cluster_policy_report_count == 1
    [rep] = result.cluster_policy_reports
    assert rep.name == "system-report"
    assert rep.pass_count == 12
    assert rep.fail_count == 0
    assert rep.result_count == 1
    assert rep.top_failing_policies == []


@pytest.mark.asyncio
async def test_rancher_cluster_policy_report_get_returns_detail() -> None:
    """ClusterPolicyReport detail should include payload."""

    result = await rancher_cluster_policy_report_get(
        report_name="system-report",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubPolicyReportsClient(),
    )

    assert result.name == "system-report"
    assert result.pass_count == 12
    assert result.payload == _CLUSTER_POLICY_REPORT_PAYLOAD
