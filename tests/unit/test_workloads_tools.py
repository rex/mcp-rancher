"""Curated workload-controller tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.workloads import (
    rancher_daemonset_get,
    rancher_daemonsets_list,
    rancher_deployment_get,
    rancher_deployments_list,
    rancher_statefulset_get,
    rancher_statefulsets_list,
)


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


@pytest.mark.asyncio
async def test_rancher_deployments_list_returns_typed_summaries() -> None:
    """Curated deployment list should expose rollout-aware summaries."""

    result = await rancher_deployments_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        ready=True,
        limit=5,
        label_selector="app=cattle-cluster-agent",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.cluster_id == "venue-local"
    assert result.namespace == "cattle-system"
    assert result.deployment_count == 1
    assert result.applied_query_params == {"limit": 5, "labelSelector": "app=cattle-cluster-agent"}
    assert result.deployments[0].ready is True
    assert result.deployments[0].rollout_complete is True


@pytest.mark.asyncio
async def test_rancher_deployment_get_returns_typed_detail() -> None:
    """Curated deployment detail should expose revision and condition detail."""

    result = await rancher_deployment_get(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.id == "cattle-system/cattle-cluster-agent"
    assert result.revision == "3"
    assert result.service_account_name == "cattle"
    assert result.conditions[0].type == "Available"


@pytest.mark.asyncio
async def test_rancher_deployments_list_handles_empty_collection() -> None:
    """Curated deployment list should handle an empty raw Kubernetes collection cleanly."""

    class EmptyDeploymentClient:
        """Return an empty deployment collection."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic empty collection."""

            assert (
                path
                == "/k8s/clusters/venue-local/apis/apps/v1/namespaces/cattle-system/deployments"
            )
            assert params is None
            return {"items": []}

    result = await rancher_deployments_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=EmptyDeploymentClient(),
    )

    assert result.deployment_count == 0
    assert result.applied_query_params == {}
    assert result.deployments == []


@pytest.mark.asyncio
async def test_rancher_daemonsets_list_returns_typed_summaries() -> None:
    """Curated daemonset list should expose scheduling-aware summaries."""

    result = await rancher_daemonsets_list(
        namespace="kube-system",
        cluster_id="venue-local",
        ready=True,
        limit=3,
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.daemonset_count == 1
    assert result.daemonsets[0].name == "kindnet"
    assert result.daemonsets[0].ready is True


@pytest.mark.asyncio
async def test_rancher_daemonsets_list_filters_not_ready_items() -> None:
    """Curated daemonset list should apply the computed readiness filter."""

    class MixedDaemonSetClient:
        """Return ready and not-ready daemonsets."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic daemonset collection."""

            assert (
                path == "/k8s/clusters/venue-local/apis/apps/v1/namespaces/kube-system/daemonsets"
            )
            assert params is None
            return {
                "items": [
                    {
                        "metadata": {"name": "ready-daemonset", "namespace": "kube-system"},
                        "spec": {
                            "template": {"spec": {"containers": [{"name": "app", "image": "demo"}]}}
                        },
                        "status": {
                            "desiredNumberScheduled": 2,
                            "numberReady": 2,
                            "updatedNumberScheduled": 2,
                        },
                    },
                    {
                        "metadata": {"name": "not-ready-daemonset", "namespace": "kube-system"},
                        "spec": {
                            "template": {"spec": {"containers": [{"name": "app", "image": "demo"}]}}
                        },
                        "status": {
                            "desiredNumberScheduled": 2,
                            "numberReady": 1,
                            "updatedNumberScheduled": 1,
                        },
                    },
                ]
            }

    result = await rancher_daemonsets_list(
        namespace="kube-system",
        cluster_id="venue-local",
        ready=False,
        instance="work",
        settings=build_settings(),
        client=MixedDaemonSetClient(),
    )

    assert result.daemonset_count == 1
    assert [daemonset.name for daemonset in result.daemonsets] == ["not-ready-daemonset"]


@pytest.mark.asyncio
async def test_rancher_daemonset_get_returns_typed_detail() -> None:
    """Curated daemonset detail should expose template and generation detail."""

    result = await rancher_daemonset_get(
        namespace="kube-system",
        daemonset_name="kindnet",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.id == "kube-system/kindnet"
    assert result.service_account_name == "kindnet"
    assert result.containers[0].image == "docker.io/kindest/kindnetd:v20240202-8f1494ea"


@pytest.mark.asyncio
async def test_rancher_statefulsets_list_returns_typed_summaries() -> None:
    """Curated statefulset list should expose rollout-aware summaries."""

    result = await rancher_statefulsets_list(
        namespace="apps",
        cluster_id="venue-local",
        field_selector="metadata.name=demo-db",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.statefulset_count == 1
    assert result.statefulsets[0].name == "demo-db"
    assert result.statefulsets[0].ready is True


@pytest.mark.asyncio
async def test_rancher_statefulsets_list_handles_empty_collection() -> None:
    """Curated statefulset list should handle an empty raw Kubernetes collection cleanly."""

    class EmptyStatefulSetClient:
        """Return an empty statefulset collection."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic empty collection."""

            assert path == "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/statefulsets"
            assert params is None
            return {"items": []}

    result = await rancher_statefulsets_list(
        namespace="apps",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=EmptyStatefulSetClient(),
    )

    assert result.statefulset_count == 0
    assert result.applied_query_params == {}
    assert result.statefulsets == []


@pytest.mark.asyncio
async def test_rancher_statefulset_get_returns_typed_detail() -> None:
    """Curated statefulset detail should expose revision and container detail."""

    result = await rancher_statefulset_get(
        namespace="apps",
        statefulset_name="demo-db",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.id == "apps/demo-db"
    assert result.current_revision == "demo-db-7f9cfb6f8c"
    assert result.update_revision == "demo-db-7f9cfb6f8c"
    assert result.containers[0].name == "db"


@pytest.mark.asyncio
async def test_rancher_deployments_list_filters_ready_items() -> None:
    """Curated deployment list should filter by computed rollout readiness."""

    class MixedDeploymentClient:
        """Deterministic workload client with ready and non-ready deployments."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return mixed deployment payloads."""

            assert (
                path
                == "/k8s/clusters/venue-local/apis/apps/v1/namespaces/cattle-system/deployments"
            )
            assert params is None
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "ready-deployment",
                            "namespace": "cattle-system",
                            "generation": 2,
                        },
                        "spec": {
                            "replicas": 1,
                            "selector": {"matchLabels": {"app": "ready"}},
                            "template": {
                                "spec": {"containers": [{"name": "app", "image": "demo"}]}
                            },
                        },
                        "status": {
                            "observedGeneration": 2,
                            "readyReplicas": 1,
                            "availableReplicas": 1,
                            "updatedReplicas": 1,
                        },
                    },
                    {
                        "metadata": {
                            "name": "not-ready-deployment",
                            "namespace": "cattle-system",
                            "generation": 2,
                        },
                        "spec": {
                            "replicas": 2,
                            "selector": {"matchLabels": {"app": "not-ready"}},
                            "template": {
                                "spec": {"containers": [{"name": "app", "image": "demo"}]}
                            },
                        },
                        "status": {
                            "observedGeneration": 2,
                            "readyReplicas": 1,
                            "availableReplicas": 1,
                            "updatedReplicas": 1,
                        },
                    },
                ]
            }

    result = await rancher_deployments_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        ready=True,
        instance="work",
        settings=build_settings(),
        client=MixedDeploymentClient(),
    )

    assert result.deployment_count == 1
    assert [deployment.name for deployment in result.deployments] == ["ready-deployment"]
