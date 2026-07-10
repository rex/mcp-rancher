"""Curated PrometheusRule tool tests (list, get, set_labels, set_annotations).

Covers PrometheusRule at ``monitoring.coreos.com/v1``.
"""

from __future__ import annotations

import pytest
from _prometheus_monitoring_support import (
    _PROMETHEUS_RULE_PAYLOAD,
    StubPrometheusMonitoringClient,
    build_settings,
)
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.prometheus_monitoring import (
    rancher_prometheus_rule_get,
    rancher_prometheus_rule_set_annotations,
    rancher_prometheus_rule_set_labels,
    rancher_prometheus_rules_list,
)


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


class StubPrometheusRuleSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the prometheus_rule set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the prometheus
    rule payload back with the supplied labels applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped PrometheusRule response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/monitoring.coreos.com/v1"
            "/namespaces/monitoring/prometheusrules/demo-rules"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-rules",
                    "namespace": "monitoring",
                    "labels": new_labels,
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
                            ],
                        },
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_prometheus_rule_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubPrometheusRuleSetLabelsClient()

    result = await rancher_prometheus_rule_set_labels(
        namespace="monitoring",
        rule_name="demo-rules",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/monitoring.coreos.com/v1"
        "/namespaces/monitoring/prometheusrules/demo-rules"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-rules"
    assert result.namespace == "monitoring"


@pytest.mark.asyncio
async def test_rancher_prometheus_rule_set_labels_emits_audit() -> None:
    """Audit record must carry operation='prometheus_rule_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_prometheus_rule_set_labels(
            namespace="monitoring",
            rule_name="demo-rules",
            labels={"app": "monitoring"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPrometheusRuleSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_prometheus_rule_set_labels"
    assert record["operation"] == "prometheus_rule_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


class StubPrometheusRuleSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the prometheus_rule set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the prometheus
    rule payload back with the supplied annotations applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped PrometheusRule response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/monitoring.coreos.com/v1"
            "/namespaces/monitoring/prometheusrules/demo-rules"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-rules",
                    "namespace": "monitoring",
                    "labels": {},
                    "annotations": new_annotations,
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
                            ],
                        },
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_prometheus_rule_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubPrometheusRuleSetAnnotationsClient()

    result = await rancher_prometheus_rule_set_annotations(
        namespace="monitoring",
        rule_name="demo-rules",
        annotations={"owner": "platform", "env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/monitoring.coreos.com/v1"
        "/namespaces/monitoring/prometheusrules/demo-rules"
    )
    # Body is exactly the narrow patch — annotations nested under target_path=metadata.
    expected_annotations = {"owner": "platform", "env": "prod"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-rules"
    assert result.namespace == "monitoring"


@pytest.mark.asyncio
async def test_rancher_prometheus_rule_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='prometheus_rule_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_prometheus_rule_set_annotations(
            namespace="monitoring",
            rule_name="demo-rules",
            annotations={"team": "sre"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPrometheusRuleSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_prometheus_rule_set_annotations"
    assert record["operation"] == "prometheus_rule_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
