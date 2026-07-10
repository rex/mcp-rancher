"""Curated PersistentVolume tool tests (list/get + set_labels/set_annotations)."""

from __future__ import annotations

import pytest
from _storage_support import StubRawK8sClient, build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.storage import (
    rancher_persistent_volume_get,
    rancher_persistent_volume_set_annotations,
    rancher_persistent_volume_set_labels,
    rancher_persistent_volumes_list,
)


@pytest.mark.asyncio
async def test_rancher_persistent_volumes_list_returns_typed_summaries() -> None:
    """Curated persistent-volume list should expose typed volume summaries."""

    result = await rancher_persistent_volumes_list(
        cluster_id="venue-local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.cluster_id == "venue-local"
    assert result.volume_count == 1
    assert result.persistent_volumes[0].name == "pvc-demo"
    assert result.persistent_volumes[0].volume_source_type == "hostPath"


@pytest.mark.asyncio
async def test_rancher_persistent_volume_get_returns_typed_detail() -> None:
    """Curated persistent-volume detail should expose node and provisioner detail."""

    result = await rancher_persistent_volume_get(
        volume_name="pvc-demo",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.name == "pvc-demo"
    assert result.provisioner == "rancher.io/local-path"
    assert result.node_hostnames == ["venue-worker-1"]


# =====================================================================
# PersistentVolume set_labels (patch)
# =====================================================================

_PATCHED_PV_PAYLOAD: dict[str, object] = {
    "metadata": {
        "name": "pvc-demo",
        "labels": {"env": "prod"},
        "annotations": {
            "pv.kubernetes.io/provisioned-by": "rancher.io/local-path",
        },
        "finalizers": ["kubernetes.io/pv-protection"],
    },
    "spec": {
        "capacity": {"storage": "128Mi"},
        "storageClassName": "standard",
        "claimRef": {
            "namespace": "storage-validation",
            "name": "demo-claim",
        },
        "persistentVolumeReclaimPolicy": "Delete",
        "accessModes": ["ReadWriteOnce"],
        "volumeMode": "Filesystem",
        "hostPath": {"path": "/var/lib/demo"},
    },
    "status": {
        "phase": "Bound",
    },
}


class StubPersistentVolumeSetLabelsClient:
    """Patch-capable stub for PersistentVolume set_labels.

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

        expected_path = "/k8s/clusters/local/api/v1/persistentvolumes/pvc-demo"
        if path == expected_path:
            assert params is None
            return _PATCHED_PV_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_persistent_volume_set_labels_round_trip() -> None:
    """PATCH path must be cluster-scoped (no namespace); body is {metadata: {labels: <map>}}."""

    reset_rate_limit_state()
    client = StubPersistentVolumeSetLabelsClient()

    result = await rancher_persistent_volume_set_labels(
        volume_name="pvc-demo",
        labels={"env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_patch_path == "/k8s/clusters/local/api/v1/persistentvolumes/pvc-demo"
    # Body is exactly the narrow patch wrapped in target_path=metadata.
    assert client.last_patch_payload == {"metadata": {"labels": {"env": "prod"}}}

    # Response is parsed through the get pipeline.
    assert result.name == "pvc-demo"
    assert result.payload == _PATCHED_PV_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_persistent_volume_set_labels_emits_audit() -> None:
    """Audit record must carry operation=persistent_volume_set_labels."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_persistent_volume_set_labels(
            volume_name="pvc-demo",
            labels={"env": "prod"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPersistentVolumeSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "persistent_volume_set_labels"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# =====================================================================
# PersistentVolume set_annotations (patch)
# =====================================================================

_PATCHED_PV_ANNOTATED_PAYLOAD: dict[str, object] = {
    "metadata": {
        "name": "pvc-demo",
        "annotations": {
            "pv.kubernetes.io/provisioned-by": "rancher.io/local-path",
            "team": "platform",
        },
        "finalizers": ["kubernetes.io/pv-protection"],
    },
    "spec": {
        "capacity": {"storage": "128Mi"},
        "storageClassName": "standard",
        "claimRef": {
            "namespace": "storage-validation",
            "name": "demo-claim",
        },
        "persistentVolumeReclaimPolicy": "Delete",
        "accessModes": ["ReadWriteOnce"],
        "volumeMode": "Filesystem",
        "hostPath": {"path": "/var/lib/demo"},
    },
    "status": {
        "phase": "Bound",
    },
}


class StubPersistentVolumeSetAnnotationsClient:
    """Patch-capable stub for PersistentVolume set_annotations.

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

        expected_path = "/k8s/clusters/local/api/v1/persistentvolumes/pvc-demo"
        if path == expected_path:
            assert params is None
            return _PATCHED_PV_ANNOTATED_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_persistent_volume_set_annotations_round_trip() -> None:
    """PATCH path must be cluster-scoped (no namespace); body is {metadata: {annotations: …}}."""

    reset_rate_limit_state()
    client = StubPersistentVolumeSetAnnotationsClient()

    result = await rancher_persistent_volume_set_annotations(
        volume_name="pvc-demo",
        annotations={"team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_patch_path == "/k8s/clusters/local/api/v1/persistentvolumes/pvc-demo"
    # Body is exactly the narrow patch wrapped in target_path=metadata.
    assert client.last_patch_payload == {"metadata": {"annotations": {"team": "platform"}}}

    # Response is parsed through the get pipeline.
    assert result.name == "pvc-demo"
    assert result.payload == _PATCHED_PV_ANNOTATED_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_persistent_volume_set_annotations_emits_audit() -> None:
    """Audit record must carry operation=persistent_volume_set_annotations."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_persistent_volume_set_annotations(
            volume_name="pvc-demo",
            annotations={"team": "platform"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPersistentVolumeSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "persistent_volume_set_annotations"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
