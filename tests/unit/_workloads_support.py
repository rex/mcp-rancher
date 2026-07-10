"""Shared setup for the curated workload tool test suites.

Extracted from ``test_workloads_tools.py`` when it was split by resource
to stay under the architecture line limit. ``build_settings`` and the
shared read stub ``StubRawK8sClient`` are consumed by every workload
list/get test module; operation-specific stubs stay with the tests that
use them.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


def build_settings() -> AppSettings:
    """Create deterministic settings for curated workload tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubRawK8sClient:
    """Deterministic raw Kubernetes proxy client for curated workload tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake raw Kubernetes workload payloads."""

        deployment_collection = (
            "/k8s/clusters/venue-local/apis/apps/v1/namespaces/cattle-system/deployments"
        )
        daemonset_collection = (
            "/k8s/clusters/venue-local/apis/apps/v1/namespaces/kube-system/daemonsets"
        )
        statefulset_collection = (
            "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/statefulsets"
        )
        replicaset_collection = "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/replicasets"

        if path == deployment_collection:
            assert params == {"limit": 5, "labelSelector": "app=cattle-cluster-agent"}
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "cattle-cluster-agent",
                            "namespace": "cattle-system",
                            "annotations": {
                                "deployment.kubernetes.io/revision": "3",
                            },
                            "generation": 4,
                        },
                        "spec": {
                            "replicas": 2,
                            "strategy": {"type": "RollingUpdate"},
                            "selector": {"matchLabels": {"app": "cattle-cluster-agent"}},
                            "template": {
                                "spec": {
                                    "serviceAccountName": "cattle",
                                    "containers": [
                                        {
                                            "name": "cluster-register",
                                            "image": "rancher/rancher-agent:v2.6.5",
                                        }
                                    ],
                                }
                            },
                        },
                        "status": {
                            "observedGeneration": 4,
                            "readyReplicas": 2,
                            "availableReplicas": 2,
                            "updatedReplicas": 2,
                        },
                    }
                ]
            }
        if path == f"{deployment_collection}/cattle-cluster-agent":
            assert params is None
            return {
                "metadata": {
                    "name": "cattle-cluster-agent",
                    "namespace": "cattle-system",
                    "annotations": {
                        "deployment.kubernetes.io/revision": "3",
                    },
                    "generation": 4,
                },
                "spec": {
                    "replicas": 2,
                    "strategy": {"type": "RollingUpdate"},
                    "selector": {"matchLabels": {"app": "cattle-cluster-agent"}},
                    "minReadySeconds": 0,
                    "template": {
                        "spec": {
                            "serviceAccountName": "cattle",
                            "containers": [
                                {
                                    "name": "cluster-register",
                                    "image": "rancher/rancher-agent:v2.6.5",
                                }
                            ],
                        }
                    },
                },
                "status": {
                    "observedGeneration": 4,
                    "readyReplicas": 2,
                    "availableReplicas": 2,
                    "updatedReplicas": 2,
                    "conditions": [
                        {
                            "type": "Available",
                            "status": "True",
                            "reason": "MinimumReplicasAvailable",
                            "message": "Deployment has minimum availability.",
                        }
                    ],
                },
            }
        if path == daemonset_collection:
            assert params == {"limit": 3}
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "kindnet",
                            "namespace": "kube-system",
                            "annotations": {
                                "deprecated.daemonset.template.generation": "1",
                            },
                            "generation": 1,
                        },
                        "spec": {
                            "updateStrategy": {"type": "RollingUpdate"},
                            "selector": {"matchLabels": {"app": "kindnet"}},
                            "template": {
                                "spec": {
                                    "serviceAccountName": "kindnet",
                                    "containers": [
                                        {
                                            "name": "kindnet-cni",
                                            "image": (
                                                "docker.io/kindest/kindnetd:v20240202-8f1494ea"
                                            ),
                                        }
                                    ],
                                }
                            },
                        },
                        "status": {
                            "observedGeneration": 1,
                            "desiredNumberScheduled": 2,
                            "currentNumberScheduled": 2,
                            "numberReady": 2,
                            "numberAvailable": 2,
                            "updatedNumberScheduled": 2,
                        },
                    }
                ]
            }
        if path == f"{daemonset_collection}/kindnet":
            assert params is None
            return {
                "metadata": {
                    "name": "kindnet",
                    "namespace": "kube-system",
                    "annotations": {
                        "deprecated.daemonset.template.generation": "1",
                    },
                    "generation": 1,
                },
                "spec": {
                    "updateStrategy": {"type": "RollingUpdate"},
                    "selector": {"matchLabels": {"app": "kindnet"}},
                    "template": {
                        "spec": {
                            "serviceAccountName": "kindnet",
                            "containers": [
                                {
                                    "name": "kindnet-cni",
                                    "image": ("docker.io/kindest/kindnetd:v20240202-8f1494ea"),
                                }
                            ],
                        }
                    },
                },
                "status": {
                    "observedGeneration": 1,
                    "desiredNumberScheduled": 2,
                    "currentNumberScheduled": 2,
                    "numberReady": 2,
                    "numberAvailable": 2,
                    "updatedNumberScheduled": 2,
                },
            }
        if path == statefulset_collection:
            assert params == {"fieldSelector": "metadata.name=demo-db"}
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "demo-db",
                            "namespace": "apps",
                            "annotations": {
                                "controller.kubernetes.io/pod-deletion-cost": "100",
                            },
                            "generation": 2,
                        },
                        "spec": {
                            "replicas": 1,
                            "serviceName": "demo-db",
                            "updateStrategy": {"type": "RollingUpdate"},
                            "selector": {"matchLabels": {"app": "demo-db"}},
                            "template": {
                                "spec": {
                                    "serviceAccountName": "default",
                                    "containers": [
                                        {
                                            "name": "db",
                                            "image": "postgres:16",
                                        }
                                    ],
                                }
                            },
                        },
                        "status": {
                            "observedGeneration": 2,
                            "readyReplicas": 1,
                            "currentReplicas": 1,
                            "updatedReplicas": 1,
                            "availableReplicas": 1,
                            "currentRevision": "demo-db-7f9cfb6f8c",
                            "updateRevision": "demo-db-7f9cfb6f8c",
                        },
                    }
                ]
            }
        if path == f"{statefulset_collection}/demo-db":
            assert params is None
            return {
                "metadata": {
                    "name": "demo-db",
                    "namespace": "apps",
                    "annotations": {
                        "controller.kubernetes.io/pod-deletion-cost": "100",
                    },
                    "generation": 2,
                },
                "spec": {
                    "replicas": 1,
                    "serviceName": "demo-db",
                    "updateStrategy": {"type": "RollingUpdate"},
                    "selector": {"matchLabels": {"app": "demo-db"}},
                    "template": {
                        "spec": {
                            "serviceAccountName": "default",
                            "containers": [
                                {
                                    "name": "db",
                                    "image": "postgres:16",
                                }
                            ],
                        }
                    },
                },
                "status": {
                    "observedGeneration": 2,
                    "readyReplicas": 1,
                    "currentReplicas": 1,
                    "updatedReplicas": 1,
                    "availableReplicas": 1,
                    "currentRevision": "demo-db-7f9cfb6f8c",
                    "updateRevision": "demo-db-7f9cfb6f8c",
                },
            }
        if path == replicaset_collection:
            assert params == {"limit": 5}
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "nginx-rs",
                            "namespace": "apps",
                            "annotations": {
                                "deployment.kubernetes.io/desired-replicas": "3",
                            },
                        },
                        "spec": {
                            "replicas": 3,
                            "selector": {"matchLabels": {"app": "nginx"}},
                            "template": {
                                "spec": {
                                    "containers": [
                                        {
                                            "name": "nginx",
                                            "image": "nginx:1.25",
                                        }
                                    ],
                                }
                            },
                        },
                        "status": {
                            "observedGeneration": 1,
                            "replicas": 3,
                            "readyReplicas": 3,
                            "availableReplicas": 3,
                            "fullyLabeledReplicas": 3,
                        },
                    }
                ]
            }
        if path == f"{replicaset_collection}/nginx-rs":
            assert params is None
            return {
                "metadata": {
                    "name": "nginx-rs",
                    "namespace": "apps",
                    "annotations": {
                        "deployment.kubernetes.io/desired-replicas": "3",
                    },
                },
                "spec": {
                    "replicas": 3,
                    "selector": {"matchLabels": {"app": "nginx"}},
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "nginx",
                                    "image": "nginx:1.25",
                                }
                            ],
                        }
                    },
                },
                "status": {
                    "observedGeneration": 1,
                    "replicas": 3,
                    "readyReplicas": 3,
                    "availableReplicas": 3,
                    "fullyLabeledReplicas": 3,
                },
            }
        raise AssertionError(f"unexpected raw K8s path: {path}")

    async def get_text(
        self,
        path: str,
        params: object = None,
    ) -> str:
        """Reject unexpected text requests in curated workload tests."""

        raise AssertionError(f"unexpected text path: {path} with params={params!r}")

    async def post_json(
        self,
        path: str,
        payload: object = None,
        params: object = None,
    ) -> dict[str, object]:
        """Reject unexpected POST requests in curated workload tests."""

        raise AssertionError(
            f"unexpected POST path: {path} with payload={payload!r} params={params!r}"
        )
