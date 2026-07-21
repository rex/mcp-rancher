"""Curated StorageClass mutation tests (set_labels/set_annotations patches)."""

from __future__ import annotations

import pytest
from _storage_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.storage import (
    rancher_storage_class_set_annotations,
    rancher_storage_class_set_labels,
)

# =====================================================================
# StorageClass set_labels (patch)
# =====================================================================

_PATCHED_STORAGE_CLASS_PAYLOAD: dict[str, object] = {
    "metadata": {
        "name": "standard",
        "labels": {"env": "prod"},
        "annotations": {
            "storageclass.kubernetes.io/is-default-class": "true",
        },
    },
    "provisioner": "rancher.io/local-path",
    "reclaimPolicy": "Delete",
    "volumeBindingMode": "WaitForFirstConsumer",
    "allowVolumeExpansion": False,
    "parameters": {
        "type": "local",
    },
}


class StubStorageClassSetLabelsClient:
    """Patch-capable stub for StorageClass set_labels.

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

        expected_path = "/k8s/clusters/local/apis/storage.k8s.io/v1/storageclasses/standard"
        if path == expected_path:
            assert params is None
            return _PATCHED_STORAGE_CLASS_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_storage_class_set_labels_round_trip() -> None:
    """PATCH path must be cluster-scoped (no namespace); body is {metadata: {labels: <map>}}."""

    reset_rate_limit_state()
    client = StubStorageClassSetLabelsClient()

    result = await rancher_storage_class_set_labels(
        storage_class_name="standard",
        labels={"env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/storage.k8s.io/v1/storageclasses/standard"
    )
    # Body is exactly the narrow patch wrapped in target_path=metadata.
    assert client.last_patch_payload == {"metadata": {"labels": {"env": "prod"}}}

    # Response is parsed through the get pipeline.
    assert result.name == "standard"
    assert result.ok is True
    assert result.action == "set_labels"
    assert result.changed == {"labels": {"env": "prod"}}


@pytest.mark.asyncio
async def test_rancher_storage_class_set_labels_emits_audit() -> None:
    """Audit record must carry operation=storage_class_set_labels."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_storage_class_set_labels(
            storage_class_name="standard",
            labels={"env": "prod"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubStorageClassSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "storage_class_set_labels"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# =====================================================================
# StorageClass set_annotations (patch)
# =====================================================================

_PATCHED_STORAGE_CLASS_ANNOTATED_PAYLOAD: dict[str, object] = {
    "metadata": {
        "name": "standard",
        "annotations": {
            "storageclass.kubernetes.io/is-default-class": "true",
            "team": "platform",
        },
    },
    "provisioner": "rancher.io/local-path",
    "reclaimPolicy": "Delete",
    "volumeBindingMode": "WaitForFirstConsumer",
    "allowVolumeExpansion": False,
    "parameters": {
        "type": "local",
    },
}


class StubStorageClassSetAnnotationsClient:
    """Patch-capable stub for StorageClass set_annotations.

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

        expected_path = "/k8s/clusters/local/apis/storage.k8s.io/v1/storageclasses/standard"
        if path == expected_path:
            assert params is None
            return _PATCHED_STORAGE_CLASS_ANNOTATED_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_storage_class_set_annotations_round_trip() -> None:
    """PATCH path must be cluster-scoped (no namespace); body is {metadata: {annotations: …}}."""

    reset_rate_limit_state()
    client = StubStorageClassSetAnnotationsClient()

    result = await rancher_storage_class_set_annotations(
        storage_class_name="standard",
        annotations={"team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/storage.k8s.io/v1/storageclasses/standard"
    )
    # Body is exactly the narrow patch wrapped in target_path=metadata.
    assert client.last_patch_payload == {"metadata": {"annotations": {"team": "platform"}}}

    # Response is parsed through the get pipeline.
    assert result.name == "standard"
    assert result.ok is True
    assert result.action == "set_annotations"
    assert result.changed == {"annotations": {"team": "platform"}}


@pytest.mark.asyncio
async def test_rancher_storage_class_set_annotations_emits_audit() -> None:
    """Audit record must carry operation=storage_class_set_annotations."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_storage_class_set_annotations(
            storage_class_name="standard",
            annotations={"team": "platform"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubStorageClassSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "storage_class_set_annotations"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
