"""Curated cluster-governance tool tests (HPA, ResourceQuota, LimitRange)."""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.governance import (
    rancher_horizontal_pod_autoscaler_get,
    rancher_horizontal_pod_autoscaler_set_annotations,
    rancher_horizontal_pod_autoscaler_set_labels,
    rancher_horizontal_pod_autoscalers_list,
    rancher_limit_range_get,
    rancher_limit_range_set_labels,
    rancher_limit_ranges_list,
    rancher_resource_quota_get,
    rancher_resource_quota_set_annotations,
    rancher_resource_quota_set_labels,
    rancher_resource_quotas_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for governance tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_HPA_PAYLOAD = {
    "metadata": {
        "name": "demo-hpa",
        "namespace": "demo",
        "annotations": {"app": "demo"},
    },
    "spec": {
        "scaleTargetRef": {"kind": "Deployment", "name": "demo-app"},
        "minReplicas": 2,
        "maxReplicas": 10,
        "metrics": [
            {"type": "Resource", "resource": {"name": "cpu"}},
            {"type": "Resource", "resource": {"name": "memory"}},
            {"type": "External", "external": {"metric": {"name": "queue_depth"}}},
        ],
    },
    "status": {
        "currentReplicas": 5,
        "desiredReplicas": 7,
        "conditions": [
            {"type": "AbleToScale", "status": "True"},
            {"type": "ScalingActive", "status": "True"},
        ],
    },
}

_RESOURCE_QUOTA_PAYLOAD = {
    "metadata": {
        "name": "demo-quota",
        "namespace": "demo",
        "annotations": {},
    },
    "spec": {
        "hard": {"cpu": "10", "memory": "20Gi"},
    },
    "status": {
        "hard": {"cpu": "10", "memory": "20Gi", "pods": "50"},
        "used": {"cpu": "3", "memory": "5Gi", "pods": "12"},
    },
}

_LIMIT_RANGE_PAYLOAD = {
    "metadata": {
        "name": "demo-limits",
        "namespace": "demo",
        "annotations": {},
    },
    "spec": {
        "limits": [
            {"type": "Container", "default": {"cpu": "200m"}},
            {"type": "Pod", "max": {"cpu": "4"}},
            {"type": "PersistentVolumeClaim", "max": {"storage": "100Gi"}},
        ],
    },
}


class StubGovernanceClient:
    """Deterministic raw Kubernetes proxy client for governance tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake autoscaling/v2 + core/v1 payloads."""

        autoscaling_root = "/k8s/clusters/local/apis/autoscaling/v2/namespaces/demo"
        core_root = "/k8s/clusters/local/api/v1/namespaces/demo"

        if path == f"{autoscaling_root}/horizontalpodautoscalers":
            assert params == {"limit": 5}
            return {"items": [_HPA_PAYLOAD]}
        if path == f"{autoscaling_root}/horizontalpodautoscalers/demo-hpa":
            assert params is None
            return _HPA_PAYLOAD

        if path == f"{core_root}/resourcequotas":
            assert params == {"limit": 5}
            return {"items": [_RESOURCE_QUOTA_PAYLOAD]}
        if path == f"{core_root}/resourcequotas/demo-quota":
            assert params is None
            return _RESOURCE_QUOTA_PAYLOAD

        if path == f"{core_root}/limitranges":
            assert params == {"limit": 5}
            return {"items": [_LIMIT_RANGE_PAYLOAD]}
        if path == f"{core_root}/limitranges/demo-limits":
            assert params is None
            return _LIMIT_RANGE_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscalers_list_returns_summary() -> None:
    """List should expose target ref, min/max replicas, current/desired, metric_count."""

    result = await rancher_horizontal_pod_autoscalers_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubGovernanceClient(),
    )

    assert result.horizontal_pod_autoscaler_count == 1
    [hpa] = result.horizontal_pod_autoscalers
    assert hpa.name == "demo-hpa"
    assert hpa.target_kind == "Deployment"
    assert hpa.target_name == "demo-app"
    assert hpa.min_replicas == 2
    assert hpa.max_replicas == 10
    assert hpa.current_replicas == 5
    assert hpa.desired_replicas == 7
    assert hpa.metric_count == 3
    assert hpa.able_to_scale is True
    assert hpa.scaling_active is True


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_get_returns_metric_types() -> None:
    """Detail should expose sorted unique metric types from spec.metrics[]."""

    result = await rancher_horizontal_pod_autoscaler_get(
        namespace="demo",
        hpa_name="demo-hpa",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubGovernanceClient(),
    )

    assert result.name == "demo-hpa"
    assert result.metric_types == ["External", "Resource"]
    assert result.payload == _HPA_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_resource_quotas_list_counts_hard_and_used() -> None:
    """List should count hard limits and used entries from status."""

    result = await rancher_resource_quotas_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubGovernanceClient(),
    )

    assert result.resource_quota_count == 1
    [quota] = result.resource_quotas
    assert quota.name == "demo-quota"
    # status.hard has 3 keys; status.used has 3 keys
    assert quota.hard_limit_count == 3
    assert quota.used_count == 3
    assert quota.hard_limit_keys == ["cpu", "memory", "pods"]


@pytest.mark.asyncio
async def test_rancher_resource_quota_get_returns_hard_and_used_dicts() -> None:
    """Detail should expose the full status.hard and status.used dicts."""

    result = await rancher_resource_quota_get(
        namespace="demo",
        resource_quota_name="demo-quota",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubGovernanceClient(),
    )

    assert result.name == "demo-quota"
    assert result.hard == {"cpu": "10", "memory": "20Gi", "pods": "50"}
    assert result.used == {"cpu": "3", "memory": "5Gi", "pods": "12"}


@pytest.mark.asyncio
async def test_rancher_limit_ranges_list_collects_types_present() -> None:
    """List should expose limit_count and sorted unique types_present."""

    result = await rancher_limit_ranges_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubGovernanceClient(),
    )

    assert result.limit_range_count == 1
    [lr] = result.limit_ranges
    assert lr.name == "demo-limits"
    assert lr.limit_count == 3
    assert lr.types_present == ["Container", "PersistentVolumeClaim", "Pod"]


@pytest.mark.asyncio
async def test_rancher_limit_range_get_returns_payload() -> None:
    """Detail should expose annotation keys + full payload."""

    result = await rancher_limit_range_get(
        namespace="demo",
        limit_range_name="demo-limits",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubGovernanceClient(),
    )

    assert result.name == "demo-limits"
    assert result.payload == _LIMIT_RANGE_PAYLOAD


class StubHpaSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the HPA set_labels tests.

    Captures the most recent ``patch_json`` request so tests can assert on
    the merge-patch body and path, then echoes the HPA payload back with the
    supplied labels applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped HPA response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/autoscaling/v2"
            "/namespaces/demo/horizontalpodautoscalers/demo-hpa"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-hpa",
                    "namespace": "demo",
                    "labels": new_labels,
                    "annotations": {"app": "demo"},
                },
                "spec": {
                    "scaleTargetRef": {"kind": "Deployment", "name": "demo-app"},
                    "minReplicas": 2,
                    "maxReplicas": 10,
                    "metrics": [
                        {"type": "Resource", "resource": {"name": "cpu"}},
                    ],
                },
                "status": {
                    "currentReplicas": 2,
                    "desiredReplicas": 2,
                    "conditions": [
                        {"type": "AbleToScale", "status": "True"},
                        {"type": "ScalingActive", "status": "True"},
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubHpaSetLabelsClient()

    result = await rancher_horizontal_pod_autoscaler_set_labels(
        namespace="demo",
        hpa_name="demo-hpa",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/autoscaling/v2/namespaces/demo/horizontalpodautoscalers/demo-hpa"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-hpa"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_set_labels_emits_audit() -> None:
    """Audit record must carry operation='hpa_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_horizontal_pod_autoscaler_set_labels(
            namespace="demo",
            hpa_name="demo-hpa",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubHpaSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_horizontal_pod_autoscaler_set_labels"
    assert record["operation"] == "hpa_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


class StubHpaSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the HPA set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can assert on
    the merge-patch body and path, then echoes the HPA payload back with the
    supplied annotations applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped HPA response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/autoscaling/v2"
            "/namespaces/demo/horizontalpodautoscalers/demo-hpa"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-hpa",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {
                    "scaleTargetRef": {"kind": "Deployment", "name": "demo-app"},
                    "minReplicas": 2,
                    "maxReplicas": 10,
                    "metrics": [
                        {"type": "Resource", "resource": {"name": "cpu"}},
                    ],
                },
                "status": {
                    "currentReplicas": 2,
                    "desiredReplicas": 2,
                    "conditions": [
                        {"type": "AbleToScale", "status": "True"},
                        {"type": "ScalingActive", "status": "True"},
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubHpaSetAnnotationsClient()

    result = await rancher_horizontal_pod_autoscaler_set_annotations(
        namespace="demo",
        hpa_name="demo-hpa",
        annotations={"owner": "platform", "tier": "production"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/autoscaling/v2/namespaces/demo/horizontalpodautoscalers/demo-hpa"
    )
    # Body is exactly the narrow patch — annotations nested under target_path=metadata.
    expected_annotations = {"owner": "platform", "tier": "production"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-hpa"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_horizontal_pod_autoscaler_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='hpa_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_horizontal_pod_autoscaler_set_annotations(
            namespace="demo",
            hpa_name="demo-hpa",
            annotations={"env": "staging"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubHpaSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_horizontal_pod_autoscaler_set_annotations"
    assert record["operation"] == "hpa_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


class StubResourceQuotaSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the ResourceQuota set_labels tests.

    Captures the most recent ``patch_json`` request so tests can assert on
    the merge-patch body and path, then echoes the ResourceQuota payload back
    with the supplied labels applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped ResourceQuota response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/local/api/v1/namespaces/demo/resourcequotas/demo-quota"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-quota",
                    "namespace": "demo",
                    "labels": new_labels,
                    "annotations": {},
                },
                "spec": {
                    "hard": {"cpu": "10", "memory": "20Gi"},
                },
                "status": {
                    "hard": {"cpu": "10", "memory": "20Gi", "pods": "50"},
                    "used": {"cpu": "3", "memory": "5Gi", "pods": "12"},
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_resource_quota_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubResourceQuotaSetLabelsClient()

    result = await rancher_resource_quota_set_labels(
        namespace="demo",
        resource_quota_name="demo-quota",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path (core/v1), not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/api/v1/namespaces/demo/resourcequotas/demo-quota"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-quota"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_resource_quota_set_labels_emits_audit() -> None:
    """Audit record must carry operation='resource_quota_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_resource_quota_set_labels(
            namespace="demo",
            resource_quota_name="demo-quota",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubResourceQuotaSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_resource_quota_set_labels"
    assert record["operation"] == "resource_quota_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


class StubResourceQuotaSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the ResourceQuota set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can assert on
    the merge-patch body and path, then echoes the ResourceQuota payload back
    with the supplied annotations applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped ResourceQuota response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/local/api/v1/namespaces/demo/resourcequotas/demo-quota"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-quota",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {
                    "hard": {"cpu": "10", "memory": "20Gi"},
                },
                "status": {
                    "hard": {"cpu": "10", "memory": "20Gi", "pods": "50"},
                    "used": {"cpu": "3", "memory": "5Gi", "pods": "12"},
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_resource_quota_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubResourceQuotaSetAnnotationsClient()

    result = await rancher_resource_quota_set_annotations(
        namespace="demo",
        resource_quota_name="demo-quota",
        annotations={"owner": "platform", "tier": "production"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path (core/v1), not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/api/v1/namespaces/demo/resourcequotas/demo-quota"
    )
    # Body is exactly the narrow patch — annotations nested under target_path=metadata.
    expected_annotations = {"owner": "platform", "tier": "production"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-quota"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_resource_quota_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='resource_quota_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_resource_quota_set_annotations(
            namespace="demo",
            resource_quota_name="demo-quota",
            annotations={"env": "staging"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubResourceQuotaSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_resource_quota_set_annotations"
    assert record["operation"] == "resource_quota_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


class StubLimitRangeSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the LimitRange set_labels tests.

    Captures the most recent ``patch_json`` request so tests can assert on
    the merge-patch body and path, then echoes the LimitRange payload back
    with the supplied labels applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped LimitRange response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/local/api/v1/namespaces/demo/limitranges/demo-limits"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-limits",
                    "namespace": "demo",
                    "labels": new_labels,
                    "annotations": {},
                },
                "spec": {
                    "limits": [
                        {"type": "Container", "default": {"cpu": "200m"}},
                        {"type": "Pod", "max": {"cpu": "4"}},
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_limit_range_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubLimitRangeSetLabelsClient()

    result = await rancher_limit_range_set_labels(
        namespace="demo",
        limit_range_name="demo-limits",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path (core/v1), not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/api/v1/namespaces/demo/limitranges/demo-limits"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-limits"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_limit_range_set_labels_emits_audit() -> None:
    """Audit record must carry operation='limit_range_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_limit_range_set_labels(
            namespace="demo",
            limit_range_name="demo-limits",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubLimitRangeSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_limit_range_set_labels"
    assert record["operation"] == "limit_range_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]
