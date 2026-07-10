"""Curated batch/v1 delete tool tests (Job delete, CronJob delete)."""

from __future__ import annotations

import pytest
from _batch_workloads_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.batch_workloads import (
    rancher_cron_job_delete,
    rancher_job_delete,
)

# =====================================================================
# rancher_job_delete (DESTRUCTIVE substrate)
# =====================================================================


class StubJobDeleteClient:
    """Delete-capable stub for the Job delete tests."""

    def __init__(self) -> None:
        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r}")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        del payload
        self.last_delete_path = path

        detail = "/k8s/clusters/local/apis/batch/v1/namespaces/demo/jobs/demo-job"
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-job", "kind": "jobs"},
            }
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_job_delete_refuses_wrong_confirmation_before_http() -> None:
    """Mismatched confirmation must refuse before any HTTP call."""

    reset_rate_limit_state()
    client = StubJobDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_job_delete(
            namespace="demo",
            job_name="demo-job",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete job demo-job in namespace demo" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_job_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct phrase routes to delete_json on the job detail path."""

    reset_rate_limit_state()
    client = StubJobDeleteClient()

    result = await rancher_job_delete(
        namespace="demo",
        job_name="demo-job",
        confirmation="delete job demo-job in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/batch/v1/namespaces/demo/jobs/demo-job"
    )
    assert result.deleted is True
    assert result.resource_kind == "job"
    assert result.resource_name == "demo-job"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete job demo-job in namespace demo"
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_jobs_list"]


@pytest.mark.asyncio
async def test_rancher_job_delete_emits_audit_with_outcome() -> None:
    """Both success and rejection paths must emit audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_job_delete(
            namespace="demo",
            job_name="demo-job",
            confirmation="delete job demo-job in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubJobDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "job_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_job_delete(
            namespace="demo",
            job_name="demo-job",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubJobDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "job_delete"
    assert reject_audits[0]["outcome"] == "error"


# =====================================================================
# rancher_cron_job_delete (DESTRUCTIVE substrate)
# =====================================================================


class StubCronJobDeleteClient:
    """Delete-capable raw Kubernetes proxy stub for cron_job delete tests."""

    def __init__(self) -> None:
        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        del payload
        self.last_delete_path = path
        detail = "/k8s/clusters/local/apis/batch/v1/namespaces/demo/cronjobs/nightly-cleanup"
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "nightly-cleanup", "kind": "cronjobs"},
            }
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cron_job_delete_refuses_wrong_confirmation_before_http() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubCronJobDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_cron_job_delete(
            namespace="demo",
            cron_job_name="nightly-cleanup",
            confirmation="wrong",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete cron_job nightly-cleanup in namespace demo" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_cron_job_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubCronJobDeleteClient()

    result = await rancher_cron_job_delete(
        namespace="demo",
        cron_job_name="nightly-cleanup",
        confirmation="delete cron_job nightly-cleanup in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert (
        client.last_delete_path
        == "/k8s/clusters/local/apis/batch/v1/namespaces/demo/cronjobs/nightly-cleanup"
    )
    assert result.deleted is True
    assert result.resource_kind == "cron_job"
    assert result.resource_name == "nightly-cleanup"


@pytest.mark.asyncio
async def test_rancher_cron_job_delete_emits_audit_with_outcome() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()
    with capture_logs() as success_logs:
        await rancher_cron_job_delete(
            namespace="demo",
            cron_job_name="nightly-cleanup",
            confirmation="delete cron_job nightly-cleanup in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCronJobDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "cron_job_delete"
    assert success_audits[0]["outcome"] == "success"

    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_cron_job_delete(
            namespace="demo",
            cron_job_name="nightly-cleanup",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCronJobDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "cron_job_delete"
    assert reject_audits[0]["outcome"] == "error"
