"""Shared setup for the curated governance tool test suites.

Extracted from ``test_governance_tools.py`` when it was split by resource and
operation to stay under the architecture line limit. ``build_settings``, the
read-path payloads, and the shared read stub ``StubGovernanceClient`` are
consumed by the governance list/get test module; operation-specific stubs stay
with the tests that use them.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


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
