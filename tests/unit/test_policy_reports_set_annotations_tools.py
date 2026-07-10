"""Curated PolicyReport set_annotations tool tests (PolicyReport, ClusterPolicyReport)."""

from __future__ import annotations

import pytest
from _policy_reports_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.policy_reports import (
    rancher_cluster_policy_report_set_annotations,
    rancher_policy_report_set_annotations,
)

# rancher_policy_report_set_annotations (PatchConfig substrate — metadata target)
# ==============================================================================


class StubPolicyReportSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the report
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
        """Capture the merge-patch and echo a Kubernetes-shaped PolicyReport response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2"
            "/namespaces/demo/policyreports/demo-report"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-report",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "summary": {"pass": 5, "fail": 3, "warn": 1, "error": 0, "skip": 2},
                "results": [
                    {"policy": "require-labels", "result": "fail", "rule": "check-app"},
                ],
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_policy_report_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubPolicyReportSetAnnotationsClient()

    result = await rancher_policy_report_set_annotations(
        namespace="demo",
        report_name="demo-report",
        annotations={"owner": "platform", "reviewed": "true"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2/namespaces/demo/policyreports/demo-report"
    )
    expected_annotations = {"owner": "platform", "reviewed": "true"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    assert result.name == "demo-report"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_policy_report_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='policy_report_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_policy_report_set_annotations(
            namespace="demo",
            report_name="demo-report",
            annotations={"owner": "platform"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPolicyReportSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_policy_report_set_annotations"
    assert record["operation"] == "policy_report_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


# rancher_cluster_policy_report_set_annotations (cluster-scoped, no namespace)
# ============================================================================

_PATCHED_CLUSTER_POLICY_REPORT_ANNOTATIONS_PAYLOAD = {
    "metadata": {
        "name": "system-report",
        "labels": {},
        "annotations": {"owner": "platform-team"},
    },
    "summary": {"pass": 12, "fail": 0, "warn": 0, "error": 0, "skip": 1},
    "results": [{"policy": "node-baseline", "result": "pass", "rule": "audit"}],
}


class StubClusterPolicyReportSetAnnotationsClient:
    """Cluster-scoped patch stub for ClusterPolicyReport set_annotations.

    Captures the most recent ``patch_json`` request so tests can assert on
    the merge-patch body and path, then echoes back a shaped response.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

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
        """Capture the merge-patch and echo a ClusterPolicyReport response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)
        expected_path = (
            "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2/clusterpolicyreports/system-report"
        )
        if path == expected_path:
            assert params is None
            return _PATCHED_CLUSTER_POLICY_REPORT_ANNOTATIONS_PAYLOAD
        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cluster_policy_report_set_annotations_round_trip() -> None:
    """Cluster-scoped path; body is {metadata: {annotations: <map>}}."""

    reset_rate_limit_state()
    client = StubClusterPolicyReportSetAnnotationsClient()
    result = await rancher_cluster_policy_report_set_annotations(
        report_name="system-report",
        annotations={"owner": "platform-team"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2/clusterpolicyreports/system-report"
    )
    assert client.last_patch_payload == {"metadata": {"annotations": {"owner": "platform-team"}}}
    assert result.name == "system-report"


@pytest.mark.asyncio
async def test_rancher_cluster_policy_report_set_annotations_emits_audit() -> None:
    """Audit op: cluster_policy_report_set_annotations."""

    reset_rate_limit_state()
    with capture_logs() as logs:
        await rancher_cluster_policy_report_set_annotations(
            report_name="system-report",
            annotations={"owner": "platform-team"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubClusterPolicyReportSetAnnotationsClient(),
        )
    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cluster_policy_report_set_annotations"
    assert record["operation"] == "cluster_policy_report_set_annotations"
    assert record["outcome"] == "success"
