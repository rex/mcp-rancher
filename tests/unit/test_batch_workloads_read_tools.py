"""Curated batch/v1 read tests (Jobs + CronJobs list, get)."""

from __future__ import annotations

import pytest
from _batch_workloads_support import (
    _CRON_JOB_PAYLOAD,
    _JOB_PAYLOAD,
    StubBatchClient,
    build_settings,
)

from rancher_mcp.tools.batch_workloads import (
    rancher_cron_job_get,
    rancher_cron_jobs_list,
    rancher_job_get,
    rancher_jobs_list,
)


@pytest.mark.asyncio
async def test_rancher_jobs_list_derives_complete_and_failed_terminal() -> None:
    """List should derive complete and failed_terminal from status.conditions."""

    result = await rancher_jobs_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubBatchClient(),
    )

    assert result.job_count == 1
    [job] = result.jobs
    assert job.name == "demo-job"
    assert job.parallelism == 2
    assert job.completions == 4
    assert job.backoff_limit == 6
    assert job.succeeded == 4
    assert job.failed == 1
    assert job.complete is True
    assert job.failed_terminal is False
    assert job.start_time == "2026-05-01T00:00:00Z"
    assert job.completion_time == "2026-05-01T00:05:00Z"


@pytest.mark.asyncio
async def test_rancher_job_get_returns_container_images() -> None:
    """Detail should expose sorted unique container images from the pod template."""

    result = await rancher_job_get(
        namespace="demo",
        job_name="demo-job",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubBatchClient(),
    )

    assert result.name == "demo-job"
    assert result.container_images == ["alpine:3.19", "fluent/fluent-bit:2.2"]
    assert result.payload == _JOB_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_cron_jobs_list_counts_active_jobs() -> None:
    """List should count currently-active job references from status.active."""

    result = await rancher_cron_jobs_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubBatchClient(),
    )

    assert result.cron_job_count == 1
    [cron] = result.cron_jobs
    assert cron.name == "nightly-cleanup"
    assert cron.schedule == "0 2 * * *"
    assert cron.suspend is False
    assert cron.concurrency_policy == "Forbid"
    assert cron.successful_jobs_history_limit == 3
    assert cron.failed_jobs_history_limit == 1
    assert cron.last_schedule_time == "2026-05-01T02:00:00Z"
    assert cron.last_successful_time == "2026-05-01T02:00:30Z"
    assert cron.active_job_count == 1


@pytest.mark.asyncio
async def test_rancher_cron_job_get_returns_active_names_and_images() -> None:
    """Detail should expose active_job_names + container images from jobTemplate."""

    result = await rancher_cron_job_get(
        namespace="demo",
        cron_job_name="nightly-cleanup",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubBatchClient(),
    )

    assert result.name == "nightly-cleanup"
    assert result.active_job_names == ["nightly-cleanup-1714521600"]
    assert result.container_images == ["alpine:3.19"]
    assert result.payload == _CRON_JOB_PAYLOAD
