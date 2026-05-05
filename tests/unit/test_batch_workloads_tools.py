"""Curated batch/v1 tool tests (Jobs, CronJobs)."""

from __future__ import annotations

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.batch_workloads import (
    rancher_cron_job_get,
    rancher_cron_jobs_list,
    rancher_job_get,
    rancher_jobs_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for batch_workloads tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_JOB_PAYLOAD = {
    "metadata": {
        "name": "demo-job",
        "namespace": "demo",
        "annotations": {"app": "demo"},
    },
    "spec": {
        "parallelism": 2,
        "completions": 4,
        "backoffLimit": 6,
        "template": {
            "spec": {
                "containers": [
                    {"name": "worker", "image": "alpine:3.19"},
                    {"name": "sidecar", "image": "fluent/fluent-bit:2.2"},
                ],
            },
        },
    },
    "status": {
        "active": 0,
        "succeeded": 4,
        "failed": 1,
        "startTime": "2026-05-01T00:00:00Z",
        "completionTime": "2026-05-01T00:05:00Z",
        "conditions": [
            {"type": "Complete", "status": "True"},
            {"type": "Failed", "status": "False"},
        ],
    },
}

_CRON_JOB_PAYLOAD = {
    "metadata": {
        "name": "nightly-cleanup",
        "namespace": "demo",
        "annotations": {"team": "platform"},
    },
    "spec": {
        "schedule": "0 2 * * *",
        "suspend": False,
        "concurrencyPolicy": "Forbid",
        "successfulJobsHistoryLimit": 3,
        "failedJobsHistoryLimit": 1,
        "jobTemplate": {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {"name": "cleanup", "image": "alpine:3.19"},
                        ],
                    },
                },
            },
        },
    },
    "status": {
        "lastScheduleTime": "2026-05-01T02:00:00Z",
        "lastSuccessfulTime": "2026-05-01T02:00:30Z",
        "active": [
            {"name": "nightly-cleanup-1714521600", "namespace": "demo"},
        ],
    },
}


class StubBatchClient:
    """Deterministic raw Kubernetes proxy client for batch/v1 tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake batch/v1 payloads."""

        ns_root = "/k8s/clusters/local/apis/batch/v1/namespaces/demo"

        if path == f"{ns_root}/jobs":
            assert params == {"limit": 5}
            return {"items": [_JOB_PAYLOAD]}
        if path == f"{ns_root}/jobs/demo-job":
            assert params is None
            return _JOB_PAYLOAD

        if path == f"{ns_root}/cronjobs":
            assert params == {"limit": 5}
            return {"items": [_CRON_JOB_PAYLOAD]}
        if path == f"{ns_root}/cronjobs/nightly-cleanup":
            assert params is None
            return _CRON_JOB_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")


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
