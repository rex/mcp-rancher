"""Curated Longhorn Node tool tests (list/get + set_labels/set_annotations)."""

from __future__ import annotations

import pytest
from _longhorn_support import (
    StubLonghornClient,
    build_settings,
)
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.longhorn import (
    rancher_longhorn_node_get,
    rancher_longhorn_node_set_annotations,
    rancher_longhorn_node_set_labels,
    rancher_longhorn_nodes_list,
)


@pytest.mark.asyncio
async def test_rancher_longhorn_nodes_list_derives_ready_and_schedulable() -> None:
    """List should derive ready/schedulable booleans from status.conditions."""

    result = await rancher_longhorn_nodes_list(
        namespace="longhorn-system",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubLonghornClient(),
    )

    assert result.node_count == 1
    [node] = result.nodes
    assert node.name == "worker-1"
    assert node.allow_scheduling is True
    assert node.eviction_requested is False
    assert node.tags == ["ssd", "fast"]
    assert node.ready is True
    assert node.schedulable is True
    assert node.disk_count == 2


@pytest.mark.asyncio
async def test_rancher_longhorn_node_get_aggregates_disk_storage() -> None:
    """Detail should sum storageAvailable / storageMaximum across all disks."""

    result = await rancher_longhorn_node_get(
        namespace="longhorn-system",
        node_name="worker-1",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubLonghornClient(),
    )

    assert result.name == "worker-1"
    # disk-1: 100/200, disk-2: 50/150 → totals 150/350
    assert result.storage_available_total == 150
    assert result.storage_maximum_total == 350
    assert result.disk_count == 2


# rancher_longhorn_node_set_labels (PatchConfig substrate — metadata target)
# ===========================================================================


class StubLonghornNodeSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the node set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the node
    payload back with the supplied labels applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped node response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/longhorn.io/v1beta2/namespaces/longhorn-system/nodes/worker-1"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "worker-1",
                    "namespace": "longhorn-system",
                    "labels": new_labels,
                    "annotations": {"team": "storage"},
                },
                "spec": {
                    "allowScheduling": True,
                    "evictionRequested": False,
                    "tags": ["ssd", "fast"],
                },
                "status": {
                    "conditions": [
                        {"type": "Ready", "status": "True"},
                        {"type": "Schedulable", "status": "True"},
                    ],
                    "diskStatus": {
                        "disk-1": {"storageAvailable": 100, "storageMaximum": 200},
                        "disk-2": {"storageAvailable": 50, "storageMaximum": 150},
                    },
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_longhorn_node_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubLonghornNodeSetLabelsClient()

    result = await rancher_longhorn_node_set_labels(
        namespace="longhorn-system",
        node_name="worker-1",
        labels={"env": "prod", "team": "storage"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/longhorn.io/v1beta2/namespaces/longhorn-system/nodes/worker-1"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "storage"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "worker-1"
    assert result.namespace == "longhorn-system"


@pytest.mark.asyncio
async def test_rancher_longhorn_node_set_labels_emits_audit() -> None:
    """Audit record must carry operation='longhorn_node_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_longhorn_node_set_labels(
            namespace="longhorn-system",
            node_name="worker-1",
            labels={"app": "storage"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubLonghornNodeSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_longhorn_node_set_labels"
    assert record["operation"] == "longhorn_node_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_longhorn_node_set_annotations (PatchConfig substrate — metadata target)
# =================================================================================


class StubLonghornNodeSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the node set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the node
    payload back with the supplied annotations applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped node response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/longhorn.io/v1beta2/namespaces/longhorn-system/nodes/worker-1"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "worker-1",
                    "namespace": "longhorn-system",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {
                    "allowScheduling": True,
                    "evictionRequested": False,
                    "tags": ["ssd", "fast"],
                },
                "status": {
                    "conditions": [
                        {"type": "Ready", "status": "True"},
                        {"type": "Schedulable", "status": "True"},
                    ],
                    "diskStatus": {
                        "disk-1": {"storageAvailable": 100, "storageMaximum": 200},
                        "disk-2": {"storageAvailable": 50, "storageMaximum": 150},
                    },
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_longhorn_node_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubLonghornNodeSetAnnotationsClient()

    result = await rancher_longhorn_node_set_annotations(
        namespace="longhorn-system",
        node_name="worker-1",
        annotations={"team": "storage", "owner": "ops"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/longhorn.io/v1beta2/namespaces/longhorn-system/nodes/worker-1"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_annotations = {"team": "storage", "owner": "ops"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "worker-1"
    assert result.namespace == "longhorn-system"


@pytest.mark.asyncio
async def test_rancher_longhorn_node_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='longhorn_node_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_longhorn_node_set_annotations(
            namespace="longhorn-system",
            node_name="worker-1",
            annotations={"team": "storage"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubLonghornNodeSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_longhorn_node_set_annotations"
    assert record["operation"] == "longhorn_node_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
