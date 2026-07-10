"""Curated Job metadata tool tests (set_labels, set_annotations)."""

from __future__ import annotations

import pytest
from _batch_workloads_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.batch_workloads import (
    rancher_job_set_annotations,
    rancher_job_set_labels,
)

# =====================================================================
# rancher_job_set_labels (PatchConfig substrate — metadata target)
# =====================================================================


class StubJobSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the job set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes a Job
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
        """Capture the merge-patch and echo a Kubernetes-shaped Job response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail = "/k8s/clusters/local/apis/batch/v1/namespaces/demo/jobs/demo-job"
        if path == detail:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-job",
                    "namespace": "demo",
                    "labels": new_labels,
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
                            ],
                        },
                    },
                },
                "status": {
                    "active": 0,
                    "succeeded": 4,
                    "failed": 0,
                    "startTime": "2026-05-01T00:00:00Z",
                    "completionTime": "2026-05-01T00:05:00Z",
                    "conditions": [
                        {"type": "Complete", "status": "True"},
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_job_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubJobSetLabelsClient()

    result = await rancher_job_set_labels(
        namespace="demo",
        job_name="demo-job",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/batch/v1/namespaces/demo/jobs/demo-job"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-job"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_job_set_labels_emits_audit() -> None:
    """Audit record must carry operation='job_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_job_set_labels(
            namespace="demo",
            job_name="demo-job",
            labels={"app": "batch"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubJobSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_job_set_labels"
    assert record["operation"] == "job_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# =====================================================================
# rancher_job_set_annotations (PatchConfig substrate — metadata target)
# =====================================================================


class StubJobSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the job set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes a Job
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
        """Capture the merge-patch and echo a Kubernetes-shaped Job response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail = "/k8s/clusters/local/apis/batch/v1/namespaces/demo/jobs/demo-job"
        if path == detail:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-job",
                    "namespace": "demo",
                    "annotations": new_annotations,
                },
                "spec": {
                    "parallelism": 2,
                    "completions": 4,
                    "backoffLimit": 6,
                    "template": {
                        "spec": {
                            "containers": [
                                {"name": "worker", "image": "alpine:3.19"},
                            ],
                        },
                    },
                },
                "status": {
                    "active": 0,
                    "succeeded": 4,
                    "failed": 0,
                    "startTime": "2026-05-01T00:00:00Z",
                    "completionTime": "2026-05-01T00:05:00Z",
                    "conditions": [
                        {"type": "Complete", "status": "True"},
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_job_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubJobSetAnnotationsClient()

    result = await rancher_job_set_annotations(
        namespace="demo",
        job_name="demo-job",
        annotations={"owner": "platform-team", "env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/batch/v1/namespaces/demo/jobs/demo-job"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_annotations = {"owner": "platform-team", "env": "prod"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-job"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_job_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='job_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_job_set_annotations(
            namespace="demo",
            job_name="demo-job",
            annotations={"team": "ops"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubJobSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_job_set_annotations"
    assert record["operation"] == "job_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
