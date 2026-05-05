"""Curated workload-controller tool tests."""

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.workloads import (
    rancher_daemonset_get,
    rancher_daemonsets_list,
    rancher_deployment_delete,
    rancher_deployment_get,
    rancher_deployment_scale,
    rancher_deployments_list,
    rancher_replica_set_get,
    rancher_replica_sets_list,
    rancher_statefulset_get,
    rancher_statefulset_scale,
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


# =====================================================================
# rancher_deployment_scale (PatchConfig substrate end-to-end)
# =====================================================================


class StubScaleClient:
    """Patch-capable raw Kubernetes proxy stub for the scale tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body, then echoes the deployment
    payload back with the new replica count applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The scale tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Kubernetes-shaped response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail = (
            "/k8s/clusters/venue-local/apis/apps/v1/namespaces/"
            "cattle-system/deployments/cattle-cluster-agent"
        )
        if path == detail:
            assert params is None
            spec = payload.get("spec")
            assert isinstance(spec, dict)
            new_replicas = spec.get("replicas")
            return {
                "metadata": {
                    "name": "cattle-cluster-agent",
                    "namespace": "cattle-system",
                    "annotations": {
                        "deployment.kubernetes.io/revision": "4",
                    },
                    "generation": 5,
                },
                "spec": {
                    "replicas": new_replicas,
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
                    "readyReplicas": new_replicas if isinstance(new_replicas, int) else 0,
                    "availableReplicas": new_replicas if isinstance(new_replicas, int) else 0,
                    "updatedReplicas": new_replicas if isinstance(new_replicas, int) else 0,
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_deployment_scale_sends_merge_patch_at_spec_subtree() -> None:
    """Scale must PATCH the detail path with the args nested under target_path.

    For PatchConfig.target_path='spec' and a `replicas` arg, the body
    must be {"spec": {"replicas": N}} — NOT a top-level {"replicas": N}
    and NOT a full deployment payload (that'd be apply, not patch).
    """

    reset_rate_limit_state()
    client = StubScaleClient()

    result = await rancher_deployment_scale(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        replicas=5,
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/"
        "cattle-system/deployments/cattle-cluster-agent"
    )
    # Body is exactly the narrow patch — only the changed subtree.
    assert client.last_patch_payload == {"spec": {"replicas": 5}}

    # Response is shaped through get's pipeline — same curated detail.
    assert result.id == "cattle-system/cattle-cluster-agent"
    # The echoed response carries the new replica count.
    assert result.payload is not None
    spec = result.payload.get("spec")
    assert isinstance(spec, dict)
    assert spec["replicas"] == 5


@pytest.mark.asyncio
async def test_rancher_deployment_scale_emits_audit_with_scale_op() -> None:
    """Scale audit records carry operation=deployment_scale (not _patch)."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_deployment_scale(
            namespace="cattle-system",
            deployment_name="cattle-cluster-agent",
            replicas=3,
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubScaleClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_deployment_scale"
    assert record["operation"] == "deployment_scale"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    # Audit captures arg names but never values — replicas count must
    # not appear in the record string representation.
    assert "3" not in str(record.get("arg_keys", []))
    assert "replicas" in record["arg_keys"]


# =====================================================================
# rancher_statefulset_scale (substrate generalization to a 2nd resource)
# =====================================================================


class StubStatefulSetScaleClient:
    """Patch-capable stub for the StatefulSet scale tests.

    Same shape as StubScaleClient but on the StatefulSet detail path.
    Proves the patch substrate is resource-agnostic — the same
    target_path: spec + replicas: int pattern works on any
    workload-controller resource.
    """

    def __init__(self) -> None:
        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail = "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/statefulsets/demo-db"
        if path == detail:
            assert params is None
            spec = payload.get("spec")
            assert isinstance(spec, dict)
            new_replicas = spec.get("replicas")
            return {
                "metadata": {"name": "demo-db", "namespace": "apps", "generation": 6},
                "spec": {
                    "replicas": new_replicas,
                    "serviceName": "demo-db",
                    "selector": {"matchLabels": {"app": "demo-db"}},
                    "template": {
                        "spec": {
                            "containers": [{"name": "db", "image": "postgres:16"}],
                        }
                    },
                },
                "status": {
                    "currentRevision": "demo-db-7f9cfb6f8c",
                    "updateRevision": "demo-db-7f9cfb6f8c",
                    "readyReplicas": new_replicas if isinstance(new_replicas, int) else 0,
                    "replicas": new_replicas if isinstance(new_replicas, int) else 0,
                },
            }
        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_statefulset_scale_uses_same_substrate_as_deployment_scale() -> None:
    """Statefulset scale should produce the identical merge-patch shape.

    This is the substrate-generalization test: the same PatchConfig
    pattern (target_path=spec, replicas: int) emits the same body
    shape regardless of which workload controller is being patched.
    """

    reset_rate_limit_state()
    client = StubStatefulSetScaleClient()

    result = await rancher_statefulset_scale(
        namespace="apps",
        statefulset_name="demo-db",
        replicas=3,
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/statefulsets/demo-db"
    )
    # Same narrow-patch body shape as deployment_scale: identical
    # substrate behavior across resource types.
    assert client.last_patch_payload == {"spec": {"replicas": 3}}

    # Curated detail comes back through the get pipeline.
    assert result.id == "apps/demo-db"


# =====================================================================
# rancher_deployment_delete (DESTRUCTIVE substrate on a 2nd resource)
# =====================================================================


class StubDeploymentDeleteClient:
    """Delete-capable stub for the Deployment delete tests."""

    def __init__(self) -> None:
        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r}")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        del payload
        self.last_delete_path = path

        detail = (
            "/k8s/clusters/venue-local/apis/apps/v1/namespaces/"
            "cattle-system/deployments/cattle-cluster-agent"
        )
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "cattle-cluster-agent", "kind": "deployments"},
            }
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_deployment_delete_requires_phrase_with_substituted_values() -> None:
    """Delete substrate generalizes — same confirmation-phrase guard pattern.

    The phrase template `delete deployment {deployment_name} in
    namespace {namespace}` renders into the actual values at codegen
    time; agents must echo the rendered version.
    """

    reset_rate_limit_state()
    client = StubDeploymentDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_deployment_delete(
            namespace="cattle-system",
            deployment_name="cattle-cluster-agent",
            confirmation="wrong",
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete deployment cattle-cluster-agent in namespace cattle-system" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_deployment_delete_with_correct_phrase_succeeds() -> None:
    """Correct phrase routes to delete_json on the deployment detail path."""

    reset_rate_limit_state()
    client = StubDeploymentDeleteClient()

    result = await rancher_deployment_delete(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        confirmation="delete deployment cattle-cluster-agent in namespace cattle-system",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/"
        "cattle-system/deployments/cattle-cluster-agent"
    )
    assert result.deleted is True
    assert result.resource_kind == "deployment"
    assert result.resource_name == "cattle-cluster-agent"
    assert result.namespace == "cattle-system"
    assert result.cluster_id == "venue-local"
    assert result.suggested_next_steps == ["rancher_deployments_list"]


@pytest.mark.asyncio
async def test_rancher_replica_sets_list_returns_typed_summaries() -> None:
    """Curated replicaset list should expose readiness-aware summaries."""

    result = await rancher_replica_sets_list(
        namespace="apps",
        cluster_id="venue-local",
        ready=True,
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.cluster_id == "venue-local"
    assert result.namespace == "apps"
    assert result.replica_set_count == 1
    assert result.replica_sets[0].name == "nginx-rs"
    assert result.replica_sets[0].ready is True
    assert result.replica_sets[0].replicas == 3
    assert result.replica_sets[0].ready_replicas == 3


@pytest.mark.asyncio
async def test_rancher_replica_set_get_returns_typed_detail() -> None:
    """Curated replicaset detail should expose annotation keys and full payload."""

    result = await rancher_replica_set_get(
        namespace="apps",
        replica_set_name="nginx-rs",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.id == "apps/nginx-rs"
    assert result.ready is True
    assert result.annotation_keys == ["deployment.kubernetes.io/desired-replicas"]
    assert result.container_images == ["nginx:1.25"]
    assert result.payload is not None
