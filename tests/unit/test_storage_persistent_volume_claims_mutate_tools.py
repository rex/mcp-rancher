"""Curated PersistentVolumeClaim mutation tests (set_labels/set_annotations patches)."""

from __future__ import annotations

import pytest
from _storage_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.storage import (
    rancher_persistent_volume_claim_set_annotations,
    rancher_persistent_volume_claim_set_labels,
)

# =====================================================================
# PersistentVolumeClaim set_labels (patch)
# =====================================================================

_PATCHED_PVC_PAYLOAD: dict[str, object] = {
    "metadata": {
        "name": "demo-claim",
        "namespace": "storage-validation",
        "labels": {"env": "prod"},
        "annotations": {
            "volume.kubernetes.io/selected-node": "venue-worker-1",
        },
        "finalizers": ["kubernetes.io/pvc-protection"],
    },
    "spec": {
        "storageClassName": "standard",
        "resources": {"requests": {"storage": "128Mi"}},
        "volumeName": "pvc-demo",
        "accessModes": ["ReadWriteOnce"],
        "volumeMode": "Filesystem",
    },
    "status": {
        "phase": "Bound",
        "capacity": {"storage": "128Mi"},
        "accessModes": ["ReadWriteOnce"],
    },
}


class StubPersistentVolumeClaimSetLabelsClient:
    """Patch-capable stub for PersistentVolumeClaim set_labels.

    Namespaced: path includes namespace segment.
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
            "/k8s/clusters/local/api/v1/namespaces/"
            "storage-validation/persistentvolumeclaims/demo-claim"
        )
        if path == expected_path:
            assert params is None
            return _PATCHED_PVC_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_set_labels_round_trip() -> None:
    """PATCH path must be namespaced; body is {metadata: {labels: <map>}}."""

    reset_rate_limit_state()
    client = StubPersistentVolumeClaimSetLabelsClient()

    result = await rancher_persistent_volume_claim_set_labels(
        namespace="storage-validation",
        claim_name="demo-claim",
        labels={"env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Namespaced path — includes namespace segment.
    assert client.last_patch_path == (
        "/k8s/clusters/local/api/v1/namespaces/storage-validation/persistentvolumeclaims/demo-claim"
    )
    # Body is exactly the narrow patch wrapped in target_path=metadata.
    assert client.last_patch_payload == {"metadata": {"labels": {"env": "prod"}}}

    # Response is parsed through the get pipeline.
    assert result.name == "demo-claim"
    assert result.payload == _PATCHED_PVC_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_set_labels_emits_audit() -> None:
    """Audit record must carry operation=persistent_volume_claim_set_labels."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_persistent_volume_claim_set_labels(
            namespace="storage-validation",
            claim_name="demo-claim",
            labels={"env": "prod"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPersistentVolumeClaimSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "persistent_volume_claim_set_labels"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# =====================================================================
# PersistentVolumeClaim set_annotations (patch)
# =====================================================================

_PATCHED_PVC_ANNOTATED_PAYLOAD: dict[str, object] = {
    "metadata": {
        "name": "demo-claim",
        "namespace": "storage-validation",
        "annotations": {
            "volume.kubernetes.io/selected-node": "venue-worker-1",
            "team": "platform",
        },
        "finalizers": ["kubernetes.io/pvc-protection"],
    },
    "spec": {
        "storageClassName": "standard",
        "resources": {"requests": {"storage": "128Mi"}},
        "volumeName": "pvc-demo",
        "accessModes": ["ReadWriteOnce"],
        "volumeMode": "Filesystem",
    },
    "status": {
        "phase": "Bound",
        "capacity": {"storage": "128Mi"},
        "accessModes": ["ReadWriteOnce"],
    },
}


class StubPersistentVolumeClaimSetAnnotationsClient:
    """Patch-capable stub for PersistentVolumeClaim set_annotations.

    Namespaced: path includes namespace segment.
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

        expected_path = (
            "/k8s/clusters/local/api/v1/namespaces/"
            "storage-validation/persistentvolumeclaims/demo-claim"
        )
        if path == expected_path:
            assert params is None
            return _PATCHED_PVC_ANNOTATED_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_set_annotations_round_trip() -> None:
    """PATCH path must be namespaced; body is {metadata: {annotations: <map>}}."""

    reset_rate_limit_state()
    client = StubPersistentVolumeClaimSetAnnotationsClient()

    result = await rancher_persistent_volume_claim_set_annotations(
        namespace="storage-validation",
        claim_name="demo-claim",
        annotations={"team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Namespaced path — includes namespace segment.
    assert client.last_patch_path == (
        "/k8s/clusters/local/api/v1/namespaces/storage-validation/persistentvolumeclaims/demo-claim"
    )
    # Body is exactly the narrow patch wrapped in target_path=metadata.
    assert client.last_patch_payload == {"metadata": {"annotations": {"team": "platform"}}}

    # Response is parsed through the get pipeline.
    assert result.name == "demo-claim"
    assert result.payload == _PATCHED_PVC_ANNOTATED_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_set_annotations_emits_audit() -> None:
    """Audit record must carry operation=persistent_volume_claim_set_annotations."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_persistent_volume_claim_set_annotations(
            namespace="storage-validation",
            claim_name="demo-claim",
            annotations={"team": "platform"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPersistentVolumeClaimSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "persistent_volume_claim_set_annotations"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
