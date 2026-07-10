"""Shared setup for the storage tool test suites.

Extracted from ``test_storage_tools.py`` when it was split by resource to
stay under the architecture line limit. ``build_settings`` and the shared
read stub ``StubRawK8sClient`` are consumed by every storage read-path test
module; operation-specific patch and delete stubs stay with the tests that
use them.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


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
