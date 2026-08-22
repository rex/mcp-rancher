"""Curated PersistentVolume tool tests (list/get)."""

from __future__ import annotations

import pytest
from _storage_support import StubRawK8sClient, build_settings

from rancher_mcp.tools.storage import (
    rancher_persistent_volume_get,
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
