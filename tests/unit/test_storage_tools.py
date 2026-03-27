"""Curated storage tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.storage import (
    rancher_persistent_volume_claim_get,
    rancher_persistent_volume_claims_list,
    rancher_persistent_volume_get,
    rancher_persistent_volumes_list,
    rancher_storage_class_get,
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
