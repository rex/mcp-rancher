"""Curated RuntimeClass tool tests (list/get)."""

from __future__ import annotations

import pytest
from _scheduling_support import (
    _RUNTIME_CLASS_PAYLOAD,
    StubSchedulingClient,
    build_settings,
)

from rancher_mcp.tools.scheduling import (
    rancher_runtime_class_get,
    rancher_runtime_classes_list,
)


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
# RuntimeClass set_labels (patch)
# =====================================================================

_PATCHED_RUNTIME_CLASS_PAYLOAD = {
    "metadata": {
        "name": "kata",
        "labels": {"env": "prod"},
        "annotations": {},
    },
    "handler": "kata-qemu",
    "overhead": {
        "podFixed": {"cpu": "200m", "memory": "200Mi"},
    },
    "scheduling": {
        "nodeSelector": {"runtime": "kata", "node-tier": "isolated"},
    },
}


# =====================================================================
# RuntimeClass set_annotations (patch)
# =====================================================================

_PATCHED_RUNTIME_CLASS_ANNOTATIONS_PAYLOAD = {
    "metadata": {
        "name": "kata",
        "labels": {},
        "annotations": {"managed-by": "platform-team"},
    },
    "handler": "kata-qemu",
    "overhead": {
        "podFixed": {"cpu": "200m", "memory": "200Mi"},
    },
    "scheduling": {
        "nodeSelector": {"runtime": "kata", "node-tier": "isolated"},
    },
}
