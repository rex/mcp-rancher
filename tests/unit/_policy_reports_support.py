"""Shared setup for the curated PolicyReport tool test suites.

Extracted from ``test_policy_reports_tools.py`` when it was split by
operation to stay under the architecture line limit. ``build_settings``,
the shared read stub ``StubPolicyReportsClient``, and the read payload
constants are consumed by the read-path tests; operation-specific patch
and delete stubs stay with the tests that use them.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


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
