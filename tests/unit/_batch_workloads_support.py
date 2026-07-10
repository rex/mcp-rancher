"""Shared setup for the curated batch/v1 tool test suites.

Extracted from ``test_batch_workloads_tools.py`` when it was split by
resource/operation to stay under the architecture line limit.
``build_settings``, the read-path payload constants, and the shared read
stub ``StubBatchClient`` are consumed by multiple batch_workloads test
modules; operation-specific stubs stay with the tests that use them.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


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
