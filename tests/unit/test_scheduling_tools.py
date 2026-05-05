"""Curated cluster-scheduling tool tests (PriorityClass, RuntimeClass)."""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.scheduling import (
    rancher_priority_class_get,
    rancher_priority_class_set_labels,
    rancher_priority_classes_list,
    rancher_runtime_class_get,
    rancher_runtime_classes_list,
)


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


@pytest.mark.asyncio
async def test_rancher_priority_classes_list_returns_value_and_policy() -> None:
    """List should expose value, globalDefault, preemptionPolicy, description."""

    result = await rancher_priority_classes_list(
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubSchedulingClient(),
    )

    assert result.priority_class_count == 1
    [pc] = result.priority_classes
    assert pc.name == "system-critical"
    assert pc.value == 1000000
    assert pc.global_default is False
    assert pc.preemption_policy == "PreemptLowerPriority"
    assert pc.description == "Used for system-critical pods"


@pytest.mark.asyncio
async def test_rancher_priority_class_get_returns_payload() -> None:
    """Detail should include annotation keys + full payload."""

    result = await rancher_priority_class_get(
        priority_class_name="system-critical",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubSchedulingClient(),
    )

    assert result.name == "system-critical"
    assert result.annotation_keys == ["app"]
    assert result.payload == _PRIORITY_CLASS_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_runtime_classes_list_extracts_overhead_and_selector_keys() -> None:
    """List should expose handler + overhead pod-fixed keys + scheduling node selector keys."""

    result = await rancher_runtime_classes_list(
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubSchedulingClient(),
    )

    assert result.runtime_class_count == 1
    [rc] = result.runtime_classes
    assert rc.name == "kata"
    assert rc.handler == "kata-qemu"
    assert rc.overhead_pod_fixed_keys == ["cpu", "memory"]
    assert rc.scheduling_node_selector_keys == ["node-tier", "runtime"]


@pytest.mark.asyncio
async def test_rancher_runtime_class_get_returns_payload() -> None:
    """Detail should include the full payload."""

    result = await rancher_runtime_class_get(
        runtime_class_name="kata",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubSchedulingClient(),
    )

    assert result.name == "kata"
    assert result.payload == _RUNTIME_CLASS_PAYLOAD


# =====================================================================
# PriorityClass set_labels (patch)
# =====================================================================

_PATCHED_PRIORITY_CLASS_PAYLOAD = {
    "metadata": {
        "name": "system-critical",
        "labels": {"env": "prod"},
        "annotations": {"app": "platform"},
    },
    "value": 1000000,
    "globalDefault": False,
    "preemptionPolicy": "PreemptLowerPriority",
    "description": "Used for system-critical pods",
}


class StubPriorityClassSetLabelsClient:
    """Patch-capable stub for PriorityClass set_labels.

    Cluster-scoped: no namespace segment in the path.
    Captures the most recent ``patch_json`` call for assertion.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """set_labels tests do not call GET."""

        raise AssertionError(f"unexpected get on {path!r}")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and return a fake post-patch payload."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        expected_path = (
            "/k8s/clusters/local/apis/scheduling.k8s.io/v1/priorityclasses/system-critical"
        )
        if path == expected_path:
            assert params is None
            return _PATCHED_PRIORITY_CLASS_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_priority_class_set_labels_round_trip() -> None:
    """PATCH path must be cluster-scoped (no namespace); body is {metadata: {labels: <map>}}."""

    reset_rate_limit_state()
    client = StubPriorityClassSetLabelsClient()

    result = await rancher_priority_class_set_labels(
        priority_class_name="system-critical",
        labels={"env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/scheduling.k8s.io/v1/priorityclasses/system-critical"
    )
    # Body is exactly the narrow patch wrapped in target_path=metadata.
    assert client.last_patch_payload == {"metadata": {"labels": {"env": "prod"}}}

    # Response is parsed through the get pipeline.
    assert result.name == "system-critical"
    assert result.payload == _PATCHED_PRIORITY_CLASS_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_priority_class_set_labels_emits_audit() -> None:
    """Audit record must carry operation=priority_class_set_labels."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_priority_class_set_labels(
            priority_class_name="system-critical",
            labels={"env": "prod"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPriorityClassSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "priority_class_set_labels"
    assert record["outcome"] == "success"
