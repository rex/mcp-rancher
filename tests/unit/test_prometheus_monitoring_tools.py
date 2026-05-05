"""Curated kube-prometheus-stack tool tests.

Covers PrometheusRule, ServiceMonitor, PodMonitor at
``monitoring.coreos.com/v1``.
"""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.prometheus_monitoring import (
    rancher_pod_monitor_get,
    rancher_pod_monitors_list,
    rancher_prometheus_rule_get,
    rancher_prometheus_rules_list,
    rancher_service_monitor_get,
    rancher_service_monitor_set_annotations,
    rancher_service_monitor_set_labels,
    rancher_service_monitors_list,
)


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


@pytest.mark.asyncio
async def test_rancher_prometheus_rules_list_counts_alerts_and_recordings() -> None:
    """List should split rule_count into alert_count and recording_count."""

    result = await rancher_prometheus_rules_list(
        namespace="monitoring",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubPrometheusMonitoringClient(),
    )

    assert result.prometheus_rule_count == 1
    [rule] = result.prometheus_rules
    assert rule.name == "demo-rules"
    assert rule.group_count == 2
    assert rule.rule_count == 3
    assert rule.alert_count == 2
    assert rule.recording_count == 1


@pytest.mark.asyncio
async def test_rancher_prometheus_rule_get_returns_group_and_alert_names() -> None:
    """Detail should expose group_names and alert_names lists."""

    result = await rancher_prometheus_rule_get(
        namespace="monitoring",
        rule_name="demo-rules",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubPrometheusMonitoringClient(),
    )

    assert result.name == "demo-rules"
    assert result.group_names == ["node-alerts", "recording-rules"]
    assert result.alert_names == ["NodeDiskFull", "NodeMemoryHigh"]
    assert result.annotation_keys == ["team"]
    assert result.payload == _PROMETHEUS_RULE_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_service_monitors_list_returns_summary() -> None:
    """List should expose selector match labels, endpoint count, target namespaces."""

    result = await rancher_service_monitors_list(
        namespace="monitoring",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubPrometheusMonitoringClient(),
    )

    assert result.service_monitor_count == 1
    [sm] = result.service_monitors
    assert sm.name == "demo-svc-monitor"
    assert sm.selector_match_labels == {"app": "demo"}
    assert sm.endpoint_count == 2
    assert sm.target_namespaces == ["demo-app", "demo-staging"]
    assert sm.job_label == "demo-job"


@pytest.mark.asyncio
async def test_rancher_service_monitor_get_returns_endpoint_ports() -> None:
    """Detail should expose the sorted unique port list from spec.endpoints."""

    result = await rancher_service_monitor_get(
        namespace="monitoring",
        service_monitor_name="demo-svc-monitor",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubPrometheusMonitoringClient(),
    )

    assert result.name == "demo-svc-monitor"
    assert result.endpoint_ports == ["http-metrics", "telemetry"]
    assert result.payload == _SERVICE_MONITOR_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_pod_monitors_list_returns_summary() -> None:
    """List should expose podMetricsEndpoints count and target namespaces."""

    result = await rancher_pod_monitors_list(
        namespace="monitoring",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubPrometheusMonitoringClient(),
    )

    assert result.pod_monitor_count == 1
    [pm] = result.pod_monitors
    assert pm.name == "demo-pod-monitor"
    assert pm.selector_match_labels == {"role": "worker"}
    assert pm.endpoint_count == 1
    assert pm.target_namespaces == ["demo-app"]
    assert pm.job_label == "demo-pods"


@pytest.mark.asyncio
async def test_rancher_pod_monitor_get_returns_endpoint_ports() -> None:
    """Detail should expose the sorted unique port list from spec.podMetricsEndpoints."""

    result = await rancher_pod_monitor_get(
        namespace="monitoring",
        pod_monitor_name="demo-pod-monitor",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubPrometheusMonitoringClient(),
    )

    assert result.name == "demo-pod-monitor"
    assert result.endpoint_ports == ["metrics"]
    assert result.payload == _POD_MONITOR_PAYLOAD


class StubServiceMonitorSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the service
    monitor payload back with the supplied labels applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped service monitor response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/monitoring.coreos.com/v1"
            "/namespaces/monitoring/servicemonitors/demo-svc-monitor"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-svc-monitor",
                    "namespace": "monitoring",
                    "labels": new_labels,
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

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_service_monitor_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubServiceMonitorSetLabelsClient()

    result = await rancher_service_monitor_set_labels(
        namespace="monitoring",
        service_monitor_name="demo-svc-monitor",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/monitoring.coreos.com/v1"
        "/namespaces/monitoring/servicemonitors/demo-svc-monitor"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-svc-monitor"
    assert result.namespace == "monitoring"


@pytest.mark.asyncio
async def test_rancher_service_monitor_set_labels_emits_audit() -> None:
    """Audit record must carry operation='service_monitor_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_service_monitor_set_labels(
            namespace="monitoring",
            service_monitor_name="demo-svc-monitor",
            labels={"app": "prometheus"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceMonitorSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_service_monitor_set_labels"
    assert record["operation"] == "service_monitor_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


class StubServiceMonitorSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the service
    monitor payload back with the supplied annotations applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped service monitor response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/monitoring.coreos.com/v1"
            "/namespaces/monitoring/servicemonitors/demo-svc-monitor"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-svc-monitor",
                    "namespace": "monitoring",
                    "labels": {},
                    "annotations": new_annotations,
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

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_service_monitor_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubServiceMonitorSetAnnotationsClient()

    result = await rancher_service_monitor_set_annotations(
        namespace="monitoring",
        service_monitor_name="demo-svc-monitor",
        annotations={"owner": "platform", "env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/monitoring.coreos.com/v1"
        "/namespaces/monitoring/servicemonitors/demo-svc-monitor"
    )
    # Body is exactly the narrow patch — annotations nested under target_path=metadata.
    expected_annotations = {"owner": "platform", "env": "prod"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-svc-monitor"
    assert result.namespace == "monitoring"


@pytest.mark.asyncio
async def test_rancher_service_monitor_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='service_monitor_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_service_monitor_set_annotations(
            namespace="monitoring",
            service_monitor_name="demo-svc-monitor",
            annotations={"team": "sre"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceMonitorSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_service_monitor_set_annotations"
    assert record["operation"] == "service_monitor_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
