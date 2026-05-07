"""Curated PolicyReport tool tests (PolicyReport, ClusterPolicyReport)."""

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.policy_reports import (
    rancher_cluster_policy_report_get,
    rancher_cluster_policy_report_set_annotations,
    rancher_cluster_policy_report_set_labels,
    rancher_cluster_policy_reports_list,
    rancher_policy_report_delete,
    rancher_policy_report_get,
    rancher_policy_report_set_annotations,
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


# =====================================================================
# rancher_policy_report_delete (DeleteConfig substrate)
# =====================================================================


class StubPolicyReportDeleteClient:
    """Deterministic raw Kubernetes proxy client for PolicyReport delete tests."""

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for delete requests."""

        self.last_delete_path: str | None = None

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Kubernetes Status object."""

        del payload  # unused for k8s policy_report deletes
        self.last_delete_path = path

        detail = (
            "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2/"
            "namespaces/demo/policyreports/demo-report"
        )
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-report", "kind": "policyreports"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_policy_report_delete_requires_exact_confirmation_phrase() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubPolicyReportDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_policy_report_delete(
            namespace="demo",
            report_name="demo-report",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call.
    assert "delete policy_report demo-report in namespace demo" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_policy_report_delete_with_correct_phrase_succeeds() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubPolicyReportDeleteClient()

    result = await rancher_policy_report_delete(
        namespace="demo",
        report_name="demo-report",
        confirmation="delete policy_report demo-report in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/wgpolicyk8s.io/v1alpha2/namespaces/demo/policyreports/demo-report"
    )
    assert result.deleted is True
    assert result.resource_kind == "policy_report"
    assert result.resource_name == "demo-report"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == ("delete policy_report demo-report in namespace demo")
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_policy_reports_list"]


@pytest.mark.asyncio
async def test_rancher_policy_report_delete_emits_audit_with_delete_op() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_policy_report_delete(
            namespace="demo",
            report_name="demo-report",
            confirmation="delete policy_report demo-report in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPolicyReportDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "policy_report_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_policy_report_delete(
            namespace="demo",
            report_name="demo-report",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPolicyReportDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "policy_report_delete"
    assert reject_audits[0]["outcome"] == "error"
    # Audit captures the rejection reason but never the wrong phrase value.
    assert "bad" not in reject_audits[0].get("arg_keys", [])
