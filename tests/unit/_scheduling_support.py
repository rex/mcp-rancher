"""Shared setup for the scheduling tool test suites (PriorityClass, RuntimeClass).

Extracted from ``test_scheduling_tools.py`` when it was split by resource to
stay under the architecture line limit. ``build_settings``, the read-path
payloads, and the shared read stub are consumed by every scheduling test
module; operation-specific stubs stay with the tests that use them.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


def build_settings() -> AppSettings:
    """Create deterministic settings for scheduling tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_PRIORITY_CLASS_PAYLOAD = {
    "metadata": {"name": "system-critical", "annotations": {"app": "platform"}},
    "value": 1000000,
    "globalDefault": False,
    "preemptionPolicy": "PreemptLowerPriority",
    "description": "Used for system-critical pods",
}

_RUNTIME_CLASS_PAYLOAD = {
    "metadata": {"name": "kata", "annotations": {}},
    "handler": "kata-qemu",
    "overhead": {
        "podFixed": {"cpu": "200m", "memory": "200Mi"},
    },
    "scheduling": {
        "nodeSelector": {"runtime": "kata", "node-tier": "isolated"},
    },
}


class StubSchedulingClient:
    """Deterministic raw Kubernetes proxy client for scheduling tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake scheduling primitive payloads."""

        scheduling_root = "/k8s/clusters/local/apis/scheduling.k8s.io/v1"
        node_root = "/k8s/clusters/local/apis/node.k8s.io/v1"

        if path == f"{scheduling_root}/priorityclasses":
            assert params == {"limit": 5}
            return {"items": [_PRIORITY_CLASS_PAYLOAD]}
        if path == f"{scheduling_root}/priorityclasses/system-critical":
            assert params is None
            return _PRIORITY_CLASS_PAYLOAD

        if path == f"{node_root}/runtimeclasses":
            assert params == {"limit": 5}
            return {"items": [_RUNTIME_CLASS_PAYLOAD]}
        if path == f"{node_root}/runtimeclasses/kata":
            assert params is None
            return _RUNTIME_CLASS_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")
