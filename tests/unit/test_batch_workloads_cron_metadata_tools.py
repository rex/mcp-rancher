"""Curated CronJob metadata tool tests (set_labels, set_annotations)."""

from __future__ import annotations

import pytest
from _batch_workloads_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.batch_workloads import (
    rancher_cron_job_set_annotations,
    rancher_cron_job_set_labels,
)

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


# =====================================================================
# rancher_cron_job_set_annotations (PatchConfig substrate — metadata target)
# =====================================================================


class StubCronJobSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes a CronJob
    payload back with the supplied annotations applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_annotations tests don't need GET; raise to surface accidental usage."""

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
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "nightly-cleanup",
                    "namespace": "demo",
                    "annotations": new_annotations,
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
async def test_rancher_cron_job_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubCronJobSetAnnotationsClient()

    result = await rancher_cron_job_set_annotations(
        namespace="demo",
        cron_job_name="nightly-cleanup",
        annotations={"owner": "platform-team", "env": "prod"},
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
    expected_annotations = {"owner": "platform-team", "env": "prod"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "nightly-cleanup"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_cron_job_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='cron_job_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cron_job_set_annotations(
            namespace="demo",
            cron_job_name="nightly-cleanup",
            annotations={"team": "ops"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCronJobSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cron_job_set_annotations"
    assert record["operation"] == "cron_job_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
