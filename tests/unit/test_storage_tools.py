"""Curated storage tool tests."""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.storage import (
    rancher_persistent_volume_claim_delete,
    rancher_persistent_volume_claim_get,
    rancher_persistent_volume_claim_set_annotations,
    rancher_persistent_volume_claim_set_labels,
    rancher_persistent_volume_claim_set_size,
    rancher_persistent_volume_claims_list,
    rancher_persistent_volume_get,
    rancher_persistent_volume_set_annotations,
    rancher_persistent_volume_set_labels,
    rancher_persistent_volumes_list,
    rancher_storage_class_get,
    rancher_storage_class_set_annotations,
    rancher_storage_class_set_labels,
    rancher_storage_classes_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated storage tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubRawK8sClient:
    """Deterministic raw Kubernetes proxy client for curated storage tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake raw Kubernetes storage payloads."""

        if path == "/k8s/clusters/venue-local/apis/storage.k8s.io/v1/storageclasses":
            assert params == {"limit": 5}
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "standard",
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
                ]
            }
        if path == "/k8s/clusters/venue-local/apis/storage.k8s.io/v1/storageclasses/standard":
            assert params is None
            return {
                "metadata": {
                    "name": "standard",
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
                "mountOptions": ["discard"],
            }
        if path == "/k8s/clusters/venue-local/api/v1/persistentvolumes":
            assert params == {"limit": 5}
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "pvc-demo",
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
                            "nodeAffinity": {
                                "required": {
                                    "nodeSelectorTerms": [
                                        {
                                            "matchExpressions": [
                                                {
                                                    "key": "kubernetes.io/hostname",
                                                    "values": ["venue-worker-1"],
                                                }
                                            ]
                                        }
                                    ]
                                }
                            },
                        },
                        "status": {
                            "phase": "Bound",
                        },
                    }
                ]
            }
        if path == "/k8s/clusters/venue-local/api/v1/persistentvolumes/pvc-demo":
            assert params is None
            return {
                "metadata": {
                    "name": "pvc-demo",
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
                    "nodeAffinity": {
                        "required": {
                            "nodeSelectorTerms": [
                                {
                                    "matchExpressions": [
                                        {
                                            "key": "kubernetes.io/hostname",
                                            "values": ["venue-worker-1"],
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                },
                "status": {
                    "phase": "Bound",
                },
            }
        if (
            path == "/k8s/clusters/venue-local/api/v1/namespaces/"
            "storage-validation/persistentvolumeclaims"
        ):
            assert params == {"limit": 5}
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "demo-claim",
                            "namespace": "storage-validation",
                            "annotations": {
                                "volume.kubernetes.io/selected-node": "venue-worker-1",
                            },
                            "finalizers": ["kubernetes.io/pvc-protection"],
                        },
                        "spec": {
                            "storageClassName": "standard",
                            "resources": {
                                "requests": {
                                    "storage": "128Mi",
                                }
                            },
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
                ]
            }
        if (
            path == "/k8s/clusters/venue-local/api/v1/namespaces/"
            "storage-validation/persistentvolumeclaims/demo-claim"
        ):
            assert params is None
            return {
                "metadata": {
                    "name": "demo-claim",
                    "namespace": "storage-validation",
                    "annotations": {
                        "volume.kubernetes.io/selected-node": "venue-worker-1",
                    },
                    "finalizers": ["kubernetes.io/pvc-protection"],
                },
                "spec": {
                    "storageClassName": "standard",
                    "resources": {
                        "requests": {
                            "storage": "128Mi",
                        }
                    },
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
        raise AssertionError(f"unexpected raw K8s path: {path}")


@pytest.mark.asyncio
async def test_rancher_storage_classes_list_returns_typed_summaries() -> None:
    """Curated storage-class list should expose typed storage-class summaries."""

    result = await rancher_storage_classes_list(
        cluster_id="venue-local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.cluster_id == "venue-local"
    assert result.storage_class_count == 1
    assert result.applied_query_params == {"limit": 5}
    assert result.storage_classes[0].name == "standard"
    assert result.storage_classes[0].default_class is True


@pytest.mark.asyncio
async def test_rancher_storage_class_get_returns_typed_detail() -> None:
    """Curated storage-class detail should expose annotation and mount-option detail."""

    result = await rancher_storage_class_get(
        storage_class_name="standard",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.name == "standard"
    assert result.provisioner == "rancher.io/local-path"
    assert result.mount_options == ["discard"]


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


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claims_list_returns_typed_summaries() -> None:
    """Curated PVC list should expose typed claim summaries."""

    result = await rancher_persistent_volume_claims_list(
        namespace="storage-validation",
        cluster_id="venue-local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.namespace == "storage-validation"
    assert result.claim_count == 1
    assert result.persistent_volume_claims[0].id == "storage-validation/demo-claim"
    assert result.persistent_volume_claims[0].volume_name == "pvc-demo"


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_get_returns_typed_detail() -> None:
    """Curated PVC detail should expose selected-node and finalizer detail."""

    result = await rancher_persistent_volume_claim_get(
        namespace="storage-validation",
        claim_name="demo-claim",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.id == "storage-validation/demo-claim"
    assert result.selected_node == "venue-worker-1"
    assert result.finalizers == ["kubernetes.io/pvc-protection"]


@pytest.mark.asyncio
async def test_rancher_storage_classes_list_applies_default_only_filter() -> None:
    """Curated storage-class list should filter to default classes when requested."""

    class MixedStorageClassClient:
        """Deterministic storage-class client with default and non-default entries."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return mixed storage-class payloads."""

            assert path == "/k8s/clusters/venue-local/apis/storage.k8s.io/v1/storageclasses"
            assert params is None
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "standard",
                            "annotations": {
                                "storageclass.kubernetes.io/is-default-class": "true",
                            },
                        },
                        "provisioner": "rancher.io/local-path",
                    },
                    {
                        "metadata": {
                            "name": "slow",
                            "annotations": {
                                "storageclass.kubernetes.io/is-default-class": "false",
                            },
                        },
                        "provisioner": "kubernetes.io/noop",
                    },
                ]
            }

    result = await rancher_storage_classes_list(
        cluster_id="venue-local",
        default_only=True,
        instance="work",
        settings=build_settings(),
        client=MixedStorageClassClient(),
    )

    assert result.storage_class_count == 1
    assert [storage_class.name for storage_class in result.storage_classes] == ["standard"]


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
    assert result.payload == _PATCHED_STORAGE_CLASS_PAYLOAD


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
    assert result.payload == _PATCHED_STORAGE_CLASS_ANNOTATED_PAYLOAD


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


# =====================================================================
# PersistentVolumeClaim delete
# =====================================================================


class StubPersistentVolumeClaimDeleteClient:
    """Delete-capable stub for PersistentVolumeClaim delete.

    Captures the most recent ``delete_json`` call for assertion.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """delete tests do not call GET."""

        raise AssertionError(f"unexpected get on {path!r}")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Kubernetes Status object."""

        del payload  # unused for k8s pvc deletes
        self.last_delete_path = path
        return {"apiVersion": "v1", "kind": "Status", "status": "Success"}


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_delete_refuses_wrong_confirmation() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubPersistentVolumeClaimDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_persistent_volume_claim_delete(
            namespace="storage-validation",
            claim_name="demo-claim",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete persistent_volume_claim demo-claim in namespace storage-validation" in str(
        excinfo.value
    )
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_delete_routes_to_delete_json() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubPersistentVolumeClaimDeleteClient()

    result = await rancher_persistent_volume_claim_delete(
        namespace="storage-validation",
        claim_name="demo-claim",
        confirmation="delete persistent_volume_claim demo-claim in namespace storage-validation",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/api/v1/namespaces/storage-validation/persistentvolumeclaims/demo-claim"
    )
    assert result.deleted is True
    assert result.resource_kind == "persistent_volume_claim"
    assert result.resource_name == "demo-claim"
    assert result.namespace == "storage-validation"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == (
        "delete persistent_volume_claim demo-claim in namespace storage-validation"
    )
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_persistent_volume_claims_list"]


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_delete_emits_audit() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    _good_phrase = "delete persistent_volume_claim demo-claim in namespace storage-validation"
    with capture_logs() as success_logs:
        await rancher_persistent_volume_claim_delete(
            namespace="storage-validation",
            claim_name="demo-claim",
            confirmation=_good_phrase,
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPersistentVolumeClaimDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "persistent_volume_claim_delete"
    assert success_audits[0]["outcome"] == "success"

    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_persistent_volume_claim_delete(
            namespace="storage-validation",
            claim_name="demo-claim",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPersistentVolumeClaimDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "persistent_volume_claim_delete"
    assert reject_audits[0]["outcome"] == "error"


# =====================================================================
# PersistentVolumeClaim set_size (patch)
# =====================================================================

_PATCHED_PVC_RESIZED_PAYLOAD: dict[str, object] = {
    "metadata": {
        "name": "demo-claim",
        "namespace": "storage-validation",
        "annotations": {
            "volume.kubernetes.io/selected-node": "venue-worker-1",
        },
        "finalizers": ["kubernetes.io/pvc-protection"],
    },
    "spec": {
        "storageClassName": "standard",
        "resources": {"requests": {"storage": "10Gi"}},
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


class StubPersistentVolumeClaimSetSizeClient:
    """Patch-capable stub for PersistentVolumeClaim set_size.

    Namespaced: path includes namespace segment.
    Captures the most recent ``patch_json`` call for assertion.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """set_size tests do not call GET."""

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
            return _PATCHED_PVC_RESIZED_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_set_size_round_trip() -> None:
    """PATCH path must be namespaced; body is {spec: {resources: {requests: {storage: …}}}}."""

    reset_rate_limit_state()
    client = StubPersistentVolumeClaimSetSizeClient()

    result = await rancher_persistent_volume_claim_set_size(
        namespace="storage-validation",
        claim_name="demo-claim",
        storage="10Gi",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Namespaced path — includes namespace segment.
    assert client.last_patch_path == (
        "/k8s/clusters/local/api/v1/namespaces/storage-validation/persistentvolumeclaims/demo-claim"
    )
    # Body: codegen nests dotted target_path keys (substrate evolution).
    # target_path "spec.resources.requests" -> nested {spec: {resources: {requests: {...}}}}.
    assert client.last_patch_payload == {"spec": {"resources": {"requests": {"storage": "10Gi"}}}}

    # Response is parsed through the get pipeline.
    assert result.name == "demo-claim"
    assert result.payload == _PATCHED_PVC_RESIZED_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_set_size_emits_audit() -> None:
    """Audit record must carry operation=persistent_volume_claim_set_size."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_persistent_volume_claim_set_size(
            namespace="storage-validation",
            claim_name="demo-claim",
            storage="10Gi",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPersistentVolumeClaimSetSizeClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "persistent_volume_claim_set_size"
    assert record["outcome"] == "success"
    assert "storage" in record["arg_keys"]


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
