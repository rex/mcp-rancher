"""Shared setup for the curated pod/service tool test suites.

Extracted from ``test_pods_services_tools.py`` when it was split by
resource/operation to stay under the architecture line limit.
``build_settings`` and the shared read stub ``StubSteveClient`` are
consumed by the pod/service list and get test modules; operation-specific
stubs stay with the tests that use them.
"""

from rancher_mcp.config import AppSettings


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
