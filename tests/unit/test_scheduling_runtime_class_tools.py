"""Curated RuntimeClass tool tests (list/get + set_labels/set_annotations)."""

from __future__ import annotations

import pytest
from _scheduling_support import (
    _RUNTIME_CLASS_PAYLOAD,
    StubSchedulingClient,
    build_settings,
)
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.scheduling import (
    rancher_runtime_class_get,
    rancher_runtime_class_set_annotations,
    rancher_runtime_class_set_labels,
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


class StubRuntimeClassSetLabelsClient:
    """Patch-capable stub for RuntimeClass set_labels.

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

        expected_path = "/k8s/clusters/local/apis/node.k8s.io/v1/runtimeclasses/kata"
        if path == expected_path:
            assert params is None
            return _PATCHED_RUNTIME_CLASS_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_runtime_class_set_labels_round_trip() -> None:
    """PATCH path must be cluster-scoped (no namespace); body is {metadata: {labels: <map>}}."""

    reset_rate_limit_state()
    client = StubRuntimeClassSetLabelsClient()

    result = await rancher_runtime_class_set_labels(
        runtime_class_name="kata",
        labels={"env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_patch_path == "/k8s/clusters/local/apis/node.k8s.io/v1/runtimeclasses/kata"
    # Body is exactly the narrow patch wrapped in target_path=metadata.
    assert client.last_patch_payload == {"metadata": {"labels": {"env": "prod"}}}

    # Response is parsed through the get pipeline.
    assert result.name == "kata"
    assert result.ok is True
    assert result.action == "set_labels"
    assert result.changed == {"labels": {"env": "prod"}}


@pytest.mark.asyncio
async def test_rancher_runtime_class_set_labels_emits_audit() -> None:
    """Audit record must carry operation=runtime_class_set_labels."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_runtime_class_set_labels(
            runtime_class_name="kata",
            labels={"env": "prod"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubRuntimeClassSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "runtime_class_set_labels"
    assert record["outcome"] == "success"


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


class StubRuntimeClassSetAnnotationsClient:
    """Patch-capable stub for RuntimeClass set_annotations.

    Cluster-scoped: no namespace segment in the path.
    Captures the most recent ``patch_json`` call for assertion.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """set_annotations tests do not call GET."""

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

        expected_path = "/k8s/clusters/local/apis/node.k8s.io/v1/runtimeclasses/kata"
        if path == expected_path:
            assert params is None
            return _PATCHED_RUNTIME_CLASS_ANNOTATIONS_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_runtime_class_set_annotations_round_trip() -> None:
    """PATCH path must be cluster-scoped (no namespace); body is {metadata: {annotations: …}}."""

    reset_rate_limit_state()
    client = StubRuntimeClassSetAnnotationsClient()

    result = await rancher_runtime_class_set_annotations(
        runtime_class_name="kata",
        annotations={"managed-by": "platform-team"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_patch_path == "/k8s/clusters/local/apis/node.k8s.io/v1/runtimeclasses/kata"
    # Body is exactly the narrow patch wrapped in target_path=metadata.
    assert client.last_patch_payload == {
        "metadata": {"annotations": {"managed-by": "platform-team"}}
    }

    # Response is parsed through the get pipeline.
    assert result.name == "kata"
    assert result.ok is True
    assert result.action == "set_annotations"
    assert result.changed == {"annotations": {"managed-by": "platform-team"}}


@pytest.mark.asyncio
async def test_rancher_runtime_class_set_annotations_emits_audit() -> None:
    """Audit record must carry operation=runtime_class_set_annotations."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_runtime_class_set_annotations(
            runtime_class_name="kata",
            annotations={"managed-by": "platform-team"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubRuntimeClassSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "runtime_class_set_annotations"
    assert record["outcome"] == "success"
