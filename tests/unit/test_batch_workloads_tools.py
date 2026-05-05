"""Curated batch/v1 tool tests (Jobs, CronJobs)."""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.batch_workloads import (
    rancher_cron_job_get,
    rancher_cron_job_set_labels,
    rancher_cron_job_suspend,
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


# =====================================================================
# rancher_cron_job_suspend (PatchConfig substrate — spec.suspend)
# =====================================================================


class StubCronJobSuspendClient:
    """Patch-capable raw Kubernetes proxy stub for the suspend tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body, then echoes a CronJob payload
    with ``spec.suspend`` reflecting the requested new value.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The suspend tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Kubernetes-shaped CronJob response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail = "/k8s/clusters/local/apis/batch/v1/namespaces/demo/cronjobs/nightly-cleanup"
        if path == detail:
            assert params is None
            spec = payload.get("spec")
            assert isinstance(spec, dict)
            new_suspend = spec.get("suspend")
            return {
                "metadata": {
                    "name": "nightly-cleanup",
                    "namespace": "demo",
                    "annotations": {"team": "platform"},
                },
                "spec": {
                    "schedule": "0 2 * * *",
                    "suspend": new_suspend,
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
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cron_job_suspend_round_trip() -> None:
    """Suspend must PATCH the detail path with the args nested under target_path.

    For PatchConfig.target_path='spec' and a ``suspend`` bool arg, the body
    must be exactly ``{"spec": {"suspend": true}}`` — not a flat dict and
    not the full CronJob payload.
    """

    reset_rate_limit_state()
    client = StubCronJobSuspendClient()

    result = await rancher_cron_job_suspend(
        namespace="demo",
        cron_job_name="nightly-cleanup",
        suspend=True,
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/batch/v1/namespaces/demo/cronjobs/nightly-cleanup"
    )
    # Body is exactly the narrow patch — only the changed subtree.
    assert client.last_patch_payload == {"spec": {"suspend": True}}

    # Response parses through curated detail — name must round-trip.
    assert result.name == "nightly-cleanup"
    # The echoed response carries the new suspend value.
    assert result.payload is not None
    spec = result.payload.get("spec")
    assert isinstance(spec, dict)
    assert spec["suspend"] is True


@pytest.mark.asyncio
async def test_rancher_cron_job_suspend_emits_audit_with_op() -> None:
    """Suspend audit records carry operation=cronjob_suspend (not _patch)."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cron_job_suspend(
            namespace="demo",
            cron_job_name="nightly-cleanup",
            suspend=False,
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCronJobSuspendClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cron_job_suspend"
    assert record["operation"] == "cronjob_suspend"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "suspend" in record["arg_keys"]


# =====================================================================
# rancher_cron_job_set_labels (PatchConfig substrate — metadata target)
# =====================================================================


class StubCronJobSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes a CronJob
    payload back with the supplied labels applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_labels tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Kubernetes-shaped CronJob response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail = "/k8s/clusters/local/apis/batch/v1/namespaces/demo/cronjobs/nightly-cleanup"
        if path == detail:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "nightly-cleanup",
                    "namespace": "demo",
                    "labels": new_labels,
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
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cron_job_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubCronJobSetLabelsClient()

    result = await rancher_cron_job_set_labels(
        namespace="demo",
        cron_job_name="nightly-cleanup",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/batch/v1/namespaces/demo/cronjobs/nightly-cleanup"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "nightly-cleanup"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_cron_job_set_labels_emits_audit() -> None:
    """Audit record must carry operation='cron_job_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cron_job_set_labels(
            namespace="demo",
            cron_job_name="nightly-cleanup",
            labels={"app": "batch"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCronJobSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cron_job_set_labels"
    assert record["operation"] == "cron_job_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]
