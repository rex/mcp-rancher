"""Curated pod/service tool tests."""

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.pods_services import (
    rancher_pod_get,
    rancher_pods_list,
    rancher_service_get,
    rancher_service_set_labels,
    rancher_services_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated pod/service tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubSteveClient:
    """Deterministic Steve client for curated pod/service tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake pod and service payloads."""

        if path == "/pods/cattle-system":
            assert params == {
                "limit": 2,
                "labelSelector": "app=cattle-cluster-agent",
            }
            return {
                "data": [
                    {
                        "id": "cattle-system/cattle-cluster-agent-abc",
                        "metadata": {
                            "name": "cattle-cluster-agent-abc",
                            "namespace": "cattle-system",
                            "ownerReferences": [
                                {
                                    "kind": "ReplicaSet",
                                    "name": "cattle-cluster-agent-rs",
                                }
                            ],
                        },
                        "spec": {
                            "nodeName": "venue-control-plane",
                        },
                        "status": {
                            "phase": "Running",
                            "podIP": "10.244.0.6",
                            "qosClass": "BestEffort",
                            "conditions": [
                                {"type": "Ready", "status": "True"},
                            ],
                            "containerStatuses": [
                                {
                                    "name": "cluster-register",
                                    "image": "rancher/rancher-agent:v2.6.5",
                                    "ready": True,
                                    "restartCount": 0,
                                    "state": {"running": {}},
                                }
                            ],
                        },
                    }
                ]
            }
        if path == "/pods/cattle-system/cattle-cluster-agent-abc":
            assert params is None
            return {
                "id": "cattle-system/cattle-cluster-agent-abc",
                "links": {
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/pods/cattle-system/cattle-cluster-agent-abc",
                    "view": "https://rancher.work.example.com/k8s/clusters/venue-local/api/v1/namespaces/cattle-system/pods/cattle-cluster-agent-abc",
                },
                "metadata": {
                    "name": "cattle-cluster-agent-abc",
                    "namespace": "cattle-system",
                    "ownerReferences": [
                        {
                            "kind": "ReplicaSet",
                            "name": "cattle-cluster-agent-rs",
                        }
                    ],
                },
                "spec": {
                    "nodeName": "venue-control-plane",
                    "serviceAccountName": "cattle",
                },
                "status": {
                    "phase": "Running",
                    "podIP": "10.244.0.6",
                    "hostIP": "172.20.0.4",
                    "qosClass": "BestEffort",
                    "conditions": [
                        {"type": "Ready", "status": "True"},
                        {"type": "ContainersReady", "status": "True"},
                    ],
                    "containerStatuses": [
                        {
                            "name": "cluster-register",
                            "image": "rancher/rancher-agent:v2.6.5",
                            "ready": True,
                            "restartCount": 0,
                            "state": {"running": {}},
                        }
                    ],
                },
            }
        if path == "/services/cattle-system":
            assert params == {
                "limit": 2,
                "labelSelector": "app=cattle-cluster-agent",
            }
            return {
                "data": [
                    {
                        "id": "cattle-system/cattle-cluster-agent",
                        "metadata": {
                            "name": "cattle-cluster-agent",
                            "namespace": "cattle-system",
                            "state": {
                                "name": "active",
                                "message": "Service is ready",
                            },
                        },
                        "spec": {
                            "type": "ClusterIP",
                            "clusterIP": "10.96.215.129",
                            "selector": {"app": "cattle-cluster-agent"},
                            "ports": [
                                {
                                    "name": "http",
                                    "protocol": "TCP",
                                    "port": 80,
                                    "targetPort": 80,
                                }
                            ],
                        },
                    }
                ]
            }
        if path == "/services/cattle-system/cattle-cluster-agent":
            assert params is None
            return {
                "id": "cattle-system/cattle-cluster-agent",
                "links": {
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/services/cattle-system/cattle-cluster-agent",
                    "view": "https://rancher.work.example.com/k8s/clusters/venue-local/api/v1/namespaces/cattle-system/services/cattle-cluster-agent",
                },
                "metadata": {
                    "name": "cattle-cluster-agent",
                    "namespace": "cattle-system",
                    "state": {
                        "name": "active",
                        "message": "Service is ready",
                    },
                    "relationships": [
                        {"toType": "pod", "rel": "selects"},
                        {"toType": "discovery.k8s.io.endpointslice", "rel": "owner"},
                    ],
                },
                "spec": {
                    "type": "ClusterIP",
                    "clusterIP": "10.96.215.129",
                    "selector": {"app": "cattle-cluster-agent"},
                    "sessionAffinity": "None",
                    "internalTrafficPolicy": "Cluster",
                    "externalIPs": [],
                    "ports": [
                        {
                            "name": "http",
                            "protocol": "TCP",
                            "port": 80,
                            "targetPort": 80,
                        }
                    ],
                },
            }
        raise AssertionError(f"unexpected Steve path: {path}")


@pytest.mark.asyncio
async def test_rancher_pods_list_returns_typed_summaries() -> None:
    """Curated pods list should expose typed pod summaries."""

    result = await rancher_pods_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        limit=2,
        label_selector="app=cattle-cluster-agent",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.instance == "work"
    assert result.namespace == "cattle-system"
    assert result.pod_count == 1
    assert result.applied_query_params == {
        "limit": 2,
        "labelSelector": "app=cattle-cluster-agent",
    }
    assert result.pods[0].id == "cattle-system/cattle-cluster-agent-abc"
    assert result.pods[0].ready is True
    assert result.pods[0].owner_kind == "ReplicaSet"


@pytest.mark.asyncio
async def test_rancher_pod_get_returns_typed_detail() -> None:
    """Curated pod detail should expose container and condition detail."""

    result = await rancher_pod_get(
        namespace="cattle-system",
        pod_name="cattle-cluster-agent-abc",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.id == "cattle-system/cattle-cluster-agent-abc"
    assert result.host_ip == "172.20.0.4"
    assert result.service_account_name == "cattle"
    assert result.containers[0].name == "cluster-register"
    assert "view" in result.link_keys


@pytest.mark.asyncio
async def test_rancher_pods_list_filters_phase_and_handles_sparse_status() -> None:
    """Curated pods list should filter on computed pod phase without crashing on sparse status."""

    class MixedPodClient:
        """Return mixed pod phases with one sparse status payload."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic pod collection."""

            assert path == "/pods/cattle-system"
            assert params is None
            return {
                "data": [
                    {
                        "id": "cattle-system/running-pod",
                        "metadata": {"name": "running-pod", "namespace": "cattle-system"},
                        "status": {"phase": "Running"},
                    },
                    {
                        "id": "cattle-system/pending-pod",
                        "metadata": {"name": "pending-pod", "namespace": "cattle-system"},
                    },
                ]
            }

    result = await rancher_pods_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        phase="Running",
        instance="work",
        settings=build_settings(),
        client=MixedPodClient(),
    )

    assert result.pod_count == 1
    assert [pod.name for pod in result.pods] == ["running-pod"]


@pytest.mark.asyncio
async def test_rancher_services_list_returns_typed_summaries() -> None:
    """Curated services list should expose typed service summaries."""

    result = await rancher_services_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        limit=2,
        label_selector="app=cattle-cluster-agent",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.instance == "work"
    assert result.namespace == "cattle-system"
    assert result.service_count == 1
    assert result.applied_query_params == {
        "limit": 2,
        "labelSelector": "app=cattle-cluster-agent",
    }
    assert result.services[0].id == "cattle-system/cattle-cluster-agent"
    assert result.services[0].service_type == "ClusterIP"


@pytest.mark.asyncio
async def test_rancher_services_list_handles_empty_collection() -> None:
    """Curated services list should handle an empty namespace collection cleanly."""

    class EmptyServiceClient:
        """Return an empty service collection."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic empty collection."""

            assert path == "/services/cattle-system"
            assert params is None
            return {"data": []}

    result = await rancher_services_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=EmptyServiceClient(),
    )

    assert result.service_count == 0
    assert result.applied_query_params == {}
    assert result.services == []


@pytest.mark.asyncio
async def test_rancher_service_get_returns_typed_detail() -> None:
    """Curated service detail should expose relationships, ports, and link keys."""

    result = await rancher_service_get(
        namespace="cattle-system",
        service_name="cattle-cluster-agent",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.id == "cattle-system/cattle-cluster-agent"
    assert result.state_name == "active"
    assert result.session_affinity == "None"
    assert result.relationship_types == [
        "discovery.k8s.io.endpointslice",
        "owner",
        "pod",
        "selects",
    ]
    assert result.ports[0].target_port == "80"
    assert "view" in result.link_keys


# rancher_service_set_labels
# =====================================================================


class StubServiceSetLabelsClient:
    """Patch-capable Steve stub for the service set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the service
    payload back with the supplied labels applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_labels tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Steve-shaped service response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/services/demo/demo-service"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "id": "demo/demo-service",
                "metadata": {
                    "name": "demo-service",
                    "namespace": "demo",
                    "labels": new_labels,
                },
                "spec": {
                    "type": "ClusterIP",
                    "clusterIP": "10.96.1.1",
                    "ports": [
                        {
                            "name": "http",
                            "protocol": "TCP",
                            "port": 80,
                            "targetPort": 8080,
                        }
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_service_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubServiceSetLabelsClient()

    result = await rancher_service_set_labels(
        namespace="demo",
        service_name="demo-service",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == "/services/demo/demo-service"
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-service"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_service_set_labels_emits_audit() -> None:
    """Audit record must carry operation='service_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_service_set_labels(
            namespace="demo",
            service_name="demo-service",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_service_set_labels"
    assert record["operation"] == "service_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]
