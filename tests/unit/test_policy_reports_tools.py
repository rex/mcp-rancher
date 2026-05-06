"""Curated PolicyReport tool tests (PolicyReport, ClusterPolicyReport)."""

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.policy_reports import (
    rancher_cluster_policy_report_get,
    rancher_cluster_policy_report_set_labels,
    rancher_cluster_policy_reports_list,
    rancher_policy_report_get,
    rancher_policy_report_set_labels,
    rancher_policy_reports_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for policy_reports tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_POLICY_REPORT_PAYLOAD = {
    "metadata": {
        "name": "demo-report",
        "namespace": "demo",
        "annotations": {"engine": "kyverno"},
    },
    "summary": {
        "pass": 5,
        "fail": 3,
        "warn": 1,
        "error": 0,
        "skip": 2,
    },
    "results": [
        {"policy": "require-labels", "result": "pass", "rule": "check-app"},
        {"policy": "require-labels", "result": "fail", "rule": "check-app"},
        {"policy": "disallow-latest", "result": "fail", "rule": "tag"},
        {"policy": "disallow-latest", "result": "fail", "rule": "tag"},
        {"policy": "require-resources", "result": "pass", "rule": "limits"},
        {"policy": "require-resources", "result": "warn", "rule": "limits"},
    ],
}

_CLUSTER_POLICY_REPORT_PAYLOAD = {
    "metadata": {"name": "system-report", "annotations": {}},
    "summary": {
        "pass": 12,
        "fail": 0,
        "warn": 0,
        "error": 0,
        "skip": 1,
    },
    "results": [
        {"policy": "node-baseline", "result": "pass", "rule": "audit"},
    ],
}


class StubPolicyReportsClient:
    """Deterministic raw Kubernetes proxy client for policy_reports tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake PolicyReport CRD payloads."""

        ns_root = "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2/namespaces/demo"
        cluster_root = "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2"

        if path == f"{ns_root}/policyreports":
            assert params == {"limit": 5}
            return {"items": [_POLICY_REPORT_PAYLOAD]}
        if path == f"{ns_root}/policyreports/demo-report":
            assert params is None
            return _POLICY_REPORT_PAYLOAD

        if path == f"{cluster_root}/clusterpolicyreports":
            assert params == {"limit": 5}
            return {"items": [_CLUSTER_POLICY_REPORT_PAYLOAD]}
        if path == f"{cluster_root}/clusterpolicyreports/system-report":
            assert params is None
            return _CLUSTER_POLICY_REPORT_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")


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


# rancher_policy_report_set_labels (PatchConfig substrate — metadata target)
# =========================================================================


class StubPolicyReportSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the report
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
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-report",
                    "namespace": "demo",
                    "labels": new_labels,
                    "annotations": {"engine": "kyverno"},
                },
                "summary": {"pass": 5, "fail": 3, "warn": 1, "error": 0, "skip": 2},
                "results": [
                    {"policy": "require-labels", "result": "fail", "rule": "check-app"},
                ],
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_policy_report_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubPolicyReportSetLabelsClient()

    result = await rancher_policy_report_set_labels(
        namespace="demo",
        report_name="demo-report",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2/namespaces/demo/policyreports/demo-report"
    )
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    assert result.name == "demo-report"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_policy_report_set_labels_emits_audit() -> None:
    """Audit record must carry operation='policy_report_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_policy_report_set_labels(
            namespace="demo",
            report_name="demo-report",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPolicyReportSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_policy_report_set_labels"
    assert record["operation"] == "policy_report_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


_PATCHED_CLUSTER_POLICY_REPORT_PAYLOAD = {
    "metadata": {
        "name": "system-report",
        "labels": {"env": "prod"},
        "annotations": {},
    },
    "summary": {"pass": 12, "fail": 0, "warn": 0, "error": 0, "skip": 1},
    "results": [{"policy": "node-baseline", "result": "pass", "rule": "audit"}],
}


class StubClusterPolicyReportSetLabelsClient:
    """Cluster-scoped patch stub for ClusterPolicyReport set_labels."""

    def __init__(self) -> None:
        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r}")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)
        expected_path = (
            "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2/clusterpolicyreports/system-report"
        )
        if path == expected_path:
            assert params is None
            return _PATCHED_CLUSTER_POLICY_REPORT_PAYLOAD
        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cluster_policy_report_set_labels_round_trip() -> None:
    """Cluster-scoped path; body is {metadata: {labels: <map>}}."""

    reset_rate_limit_state()
    client = StubClusterPolicyReportSetLabelsClient()
    result = await rancher_cluster_policy_report_set_labels(
        report_name="system-report",
        labels={"env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2/clusterpolicyreports/system-report"
    )
    assert client.last_patch_payload == {"metadata": {"labels": {"env": "prod"}}}
    assert result.name == "system-report"


@pytest.mark.asyncio
async def test_rancher_cluster_policy_report_set_labels_emits_audit() -> None:
    """Audit op: cluster_policy_report_set_labels."""

    reset_rate_limit_state()
    with capture_logs() as logs:
        await rancher_cluster_policy_report_set_labels(
            report_name="system-report",
            labels={"env": "prod"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubClusterPolicyReportSetLabelsClient(),
        )
    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cluster_policy_report_set_labels"
    assert record["operation"] == "cluster_policy_report_set_labels"
    assert record["outcome"] == "success"
