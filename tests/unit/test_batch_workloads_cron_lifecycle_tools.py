"""Curated CronJob lifecycle tool tests (suspend, resume)."""

from __future__ import annotations

import pytest
from _batch_workloads_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.batch_workloads import (
    rancher_cron_job_resume,
    rancher_cron_job_suspend,
)

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
# rancher_cron_job_resume (argless PatchConfig substrate — target_value)
# =====================================================================


@pytest.mark.asyncio
async def test_rancher_cron_job_resume_round_trip_emits_argless_target_value() -> None:
    """Argless patches use target_value: body must be exactly {spec: {suspend: false}}.

    This validates substrate slice 2 (target_value support). The
    function takes no toggle arg — the verb itself encodes the
    change. Reuses StubCronJobSuspendClient since it echoes the
    submitted spec.suspend value.
    """

    reset_rate_limit_state()
    client = StubCronJobSuspendClient()

    result = await rancher_cron_job_resume(
        namespace="demo",
        cron_job_name="nightly-cleanup",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/batch/v1/namespaces/demo/cronjobs/nightly-cleanup"
    )
    # Body shape proves argless target_value works AND nested target_path works.
    # target_path: spec, target_value: {suspend: false} -> {spec: {suspend: false}}
    assert client.last_patch_payload == {"spec": {"suspend": False}}

    assert result.name == "nightly-cleanup"
    assert result.payload is not None
    spec = result.payload.get("spec")
    assert isinstance(spec, dict)
    assert spec["suspend"] is False


@pytest.mark.asyncio
async def test_rancher_cron_job_resume_emits_audit_with_resume_op() -> None:
    """Argless resume audit records carry operation='cron_job_resume'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cron_job_resume(
            namespace="demo",
            cron_job_name="nightly-cleanup",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCronJobSuspendClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cron_job_resume"
    assert record["operation"] == "cron_job_resume"
    assert record["outcome"] == "success"
    # Argless patches have no slice-specific args — only infrastructure kwargs.
    # Specifically: no `suspend`, no `labels`, no `annotations`.
    assert "suspend" not in record["arg_keys"]
    assert "labels" not in record["arg_keys"]
    assert "annotations" not in record["arg_keys"]
