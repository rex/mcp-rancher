"""Curated PriorityClass tool tests (list/get)."""

from __future__ import annotations

import pytest
from _scheduling_support import (
    _PRIORITY_CLASS_PAYLOAD,
    StubSchedulingClient,
    build_settings,
)

from rancher_mcp.tools.scheduling import (
    rancher_priority_class_get,
    rancher_priority_classes_list,
)


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


# =====================================================================
# PriorityClass set_annotations (patch)
# =====================================================================

_PATCHED_PRIORITY_CLASS_ANNOTATIONS_PAYLOAD = {
    "metadata": {
        "name": "system-critical",
        "labels": {},
        "annotations": {"managed-by": "platform-team"},
    },
    "value": 1000000,
    "globalDefault": False,
    "preemptionPolicy": "PreemptLowerPriority",
    "description": "Used for system-critical pods",
}
