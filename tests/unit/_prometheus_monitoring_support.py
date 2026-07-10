"""Shared setup for the curated kube-prometheus-stack tool test suites.

Extracted from ``test_prometheus_monitoring_tools.py`` when it was split by
resource/operation to stay under the architecture line limit. ``build_settings``,
the CRD payload constants, and the shared read stub
``StubPrometheusMonitoringClient`` are consumed by the list/get test modules;
operation-specific patch/delete stubs stay with the tests that use them.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


def build_settings() -> AppSettings:
    """Create deterministic settings for prometheus_monitoring tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_PROMETHEUS_RULE_PAYLOAD = {
    "metadata": {
        "name": "demo-rules",
        "namespace": "monitoring",
        "annotations": {"team": "platform"},
    },
    "spec": {
        "groups": [
            {
                "name": "node-alerts",
                "rules": [
                    {
                        "alert": "NodeMemoryHigh",
                        "expr": "node_memory_used_percent > 90",
                        "for": "5m",
                    },
                    {
                        "alert": "NodeDiskFull",
                        "expr": "node_disk_used_percent > 95",
                        "for": "10m",
                    },
                ],
            },
            {
                "name": "recording-rules",
                "rules": [
                    {
                        "record": "instance:node_cpu_seconds:rate5m",
                        "expr": "rate(node_cpu_seconds_total[5m])",
                    },
                ],
            },
        ],
    },
}

_SERVICE_MONITOR_PAYLOAD = {
    "metadata": {
        "name": "demo-svc-monitor",
        "namespace": "monitoring",
        "annotations": {},
    },
    "spec": {
        "jobLabel": "demo-job",
        "selector": {"matchLabels": {"app": "demo"}},
        "namespaceSelector": {"matchNames": ["demo-app", "demo-staging"]},
        "endpoints": [
            {"port": "http-metrics", "interval": "30s"},
            {"port": "telemetry", "interval": "60s"},
        ],
    },
}

_POD_MONITOR_PAYLOAD = {
    "metadata": {
        "name": "demo-pod-monitor",
        "namespace": "monitoring",
        "annotations": {},
    },
    "spec": {
        "jobLabel": "demo-pods",
        "selector": {"matchLabels": {"role": "worker"}},
        "namespaceSelector": {"matchNames": ["demo-app"]},
        "podMetricsEndpoints": [
            {"port": "metrics", "interval": "15s"},
        ],
    },
}


class StubPrometheusMonitoringClient:
    """Deterministic raw Kubernetes proxy client for prometheus_monitoring tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake monitoring.coreos.com/v1 CRD payloads."""

        ns_root = "/k8s/clusters/local/apis/monitoring.coreos.com/v1/namespaces/monitoring"

        if path == f"{ns_root}/prometheusrules":
            assert params == {"limit": 5}
            return {"items": [_PROMETHEUS_RULE_PAYLOAD]}
        if path == f"{ns_root}/prometheusrules/demo-rules":
            assert params is None
            return _PROMETHEUS_RULE_PAYLOAD

        if path == f"{ns_root}/servicemonitors":
            assert params == {"limit": 5}
            return {"items": [_SERVICE_MONITOR_PAYLOAD]}
        if path == f"{ns_root}/servicemonitors/demo-svc-monitor":
            assert params is None
            return _SERVICE_MONITOR_PAYLOAD

        if path == f"{ns_root}/podmonitors":
            assert params == {"limit": 5}
            return {"items": [_POD_MONITOR_PAYLOAD]}
        if path == f"{ns_root}/podmonitors/demo-pod-monitor":
            assert params is None
            return _POD_MONITOR_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")
