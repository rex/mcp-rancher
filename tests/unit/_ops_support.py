"""Shared setup for the operational aggregate helper test suites.

Extracted from ``test_ops_tools.py`` when it was split by helper family
(cluster-health, failure-finders, rollups) to stay under the architecture
line limit. ``build_settings`` and the shared ``StubOpsClient`` are consumed
by every ops test module.
"""

from collections.abc import Mapping

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.ops.paths import k8s_apps_ns_path, k8s_core_ns_path, k8s_policy_ns_path


def build_settings() -> AppSettings:
    """Create deterministic settings for operational helper tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubOpsClient:
    """Deterministic management client for operational helper tools."""

    async def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Return fake Rancher and Kubernetes payloads for ops helpers."""

        if path == "/v3/clusters":
            assert params is None
            return {
                "data": [
                    {
                        "id": "local",
                        "name": "local",
                        "state": "active",
                        "provider": "imported",
                        "nodeVersion": "v1.20.15",
                        "nodeCount": 2,
                        "conditions": [{"type": "Ready", "status": "True"}],
                        "componentStatuses": [
                            {
                                "name": "scheduler",
                                "conditions": [{"type": "Healthy", "status": "True"}],
                            }
                        ],
                    },
                    {
                        "id": "edge",
                        "name": "edge",
                        "state": "provisioning",
                        "provider": "imported",
                        "nodeVersion": "v1.23.17",
                        "nodeCount": 1,
                        "conditions": [{"type": "Ready", "status": "False"}],
                    },
                ]
            }
        if path == "/v3/clusters/local":
            assert params is None
            return {
                "id": "local",
                "name": "local",
                "state": "active",
                "provider": "imported",
                "nodeVersion": "v1.20.15",
                "conditions": [
                    {"type": "Ready", "status": "True"},
                    {"type": "Provisioned", "status": "False"},
                ],
                "componentStatuses": [
                    {
                        "name": "scheduler",
                        "conditions": [{"type": "Healthy", "status": "True"}],
                    },
                    {
                        "name": "controller-manager",
                        "conditions": [
                            {
                                "type": "Healthy",
                                "status": "False",
                                "message": "failed health check",
                            }
                        ],
                    },
                ],
            }
        if path == "/v3/projects/local:p-ops":
            assert params is None
            return {
                "id": "local:p-ops",
                "name": "ops",
                "clusterId": "local",
                "state": "active",
            }
        if path == "/k8s/clusters/local/api/v1/namespaces":
            assert params == {
                "labelSelector": "field.cattle.io/projectId=p-ops",
            }
            return {
                "items": [
                    {"metadata": {"name": "default"}},
                ]
            }
        if path == "/v3/nodes":
            if params == {"clusterId": "local"}:
                return {
                    "data": [
                        {
                            "id": "local:worker-1",
                            "name": "worker-1",
                            "clusterId": "local",
                            "state": "active",
                            "worker": True,
                            "unschedulable": False,
                            "conditions": [{"type": "Ready", "status": "True"}],
                        },
                        {
                            "id": "local:cp-1",
                            "name": "cp-1",
                            "clusterId": "local",
                            "state": "active",
                            "controlPlane": True,
                            "unschedulable": True,
                            "conditions": [
                                {
                                    "type": "Ready",
                                    "status": "False",
                                    "message": "node not responding",
                                }
                            ],
                        },
                    ]
                }
            assert params is None
            return {
                "data": [
                    {
                        "id": "local:worker-1",
                        "name": "worker-1",
                        "clusterId": "local",
                        "state": "active",
                        "worker": True,
                        "unschedulable": False,
                        "conditions": [{"type": "Ready", "status": "True"}],
                    },
                    {
                        "id": "local:cp-1",
                        "name": "cp-1",
                        "clusterId": "local",
                        "state": "active",
                        "controlPlane": True,
                        "unschedulable": True,
                        "conditions": [{"type": "Ready", "status": "False"}],
                    },
                    {
                        "id": "edge:worker-1",
                        "name": "edge-worker-1",
                        "clusterId": "edge",
                        "state": "active",
                        "worker": True,
                        "unschedulable": False,
                        "conditions": [{"type": "Ready", "status": "True"}],
                    },
                ]
            }

        if path == k8s_core_ns_path("local", "default", "pods"):
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "api-0",
                            "namespace": "default",
                            "ownerReferences": [{"kind": "Deployment", "name": "api"}],
                        },
                        "spec": {"nodeName": "worker-1"},
                        "status": {
                            "phase": "Running",
                            "conditions": [{"type": "Ready", "status": "False"}],
                            "containerStatuses": [{"restartCount": 2, "state": {}}],
                        },
                    },
                    {
                        "metadata": {"name": "worker-0", "namespace": "default"},
                        "spec": {"nodeName": "worker-1"},
                        "status": {
                            "phase": "Failed",
                            "reason": "Evicted",
                            "containerStatuses": [{"restartCount": 1, "state": {}}],
                        },
                    },
                    {
                        "metadata": {"name": "healthy-0", "namespace": "default"},
                        "spec": {"nodeName": "worker-1"},
                        "status": {
                            "phase": "Running",
                            "conditions": [{"type": "Ready", "status": "True"}],
                            "containerStatuses": [{"restartCount": 0, "state": {}}],
                        },
                    },
                ]
            }
        if path == k8s_core_ns_path("local", "default", "services"):
            return {
                "items": [
                    {
                        "metadata": {"name": "web", "namespace": "default"},
                        "spec": {"type": "ClusterIP", "selector": {"app": "web"}},
                    },
                    {
                        "metadata": {"name": "node-api", "namespace": "default"},
                        "spec": {"type": "NodePort", "selector": {"app": "node-api"}},
                    },
                    {
                        "metadata": {"name": "external", "namespace": "default"},
                        "spec": {"type": "ExternalName", "selector": {"app": "external"}},
                    },
                ]
            }
        if path == k8s_core_ns_path("local", "default", "endpoints"):
            return {
                "items": [
                    {
                        "metadata": {"name": "web"},
                        "subsets": [{"addresses": [{"ip": "10.42.0.10"}]}],
                    },
                    {
                        "metadata": {"name": "node-api"},
                        "subsets": [{"notReadyAddresses": [{"ip": "10.42.0.11"}]}],
                    },
                ]
            }
        if path == k8s_core_ns_path("local", "default", "persistentvolumeclaims"):
            return {
                "items": [
                    {
                        "metadata": {"name": "cache", "namespace": "default"},
                        "spec": {
                            "storageClassName": "fast",
                            "resources": {"requests": {"storage": "10Gi"}},
                        },
                        "status": {"phase": "Pending"},
                    },
                    {
                        "metadata": {"name": "db", "namespace": "default"},
                        "spec": {
                            "storageClassName": "fast",
                            "resources": {"requests": {"storage": "20Gi"}},
                        },
                        "status": {"phase": "Bound"},
                    },
                ]
            }

        if path == k8s_apps_ns_path("local", "default", "deployments"):
            return {
                "items": [
                    {
                        "metadata": {"name": "api", "namespace": "default", "generation": 3},
                        "spec": {"replicas": 2, "paused": False},
                        "status": {
                            "readyReplicas": 2,
                            "availableReplicas": 2,
                            "updatedReplicas": 2,
                            "observedGeneration": 3,
                        },
                    },
                    {
                        "metadata": {"name": "worker", "namespace": "default", "generation": 5},
                        "spec": {"replicas": 3, "paused": False},
                        "status": {
                            "readyReplicas": 1,
                            "availableReplicas": 1,
                            "updatedReplicas": 2,
                            "observedGeneration": 5,
                            "unavailableReplicas": 2,
                        },
                    },
                ]
            }
        if path == k8s_apps_ns_path("local", "default", "daemonsets"):
            return {
                "items": [
                    {
                        "metadata": {"name": "node-agent", "namespace": "default"},
                        "status": {
                            "desiredNumberScheduled": 1,
                            "numberReady": 0,
                            "updatedNumberScheduled": 0,
                        },
                    }
                ]
            }
        if path == k8s_apps_ns_path("local", "default", "statefulsets"):
            return {
                "items": [
                    {
                        "metadata": {"name": "redis", "namespace": "default"},
                        "spec": {"replicas": 1},
                        "status": {"readyReplicas": 1, "updatedReplicas": 1},
                    },
                    {
                        "metadata": {"name": "queue", "namespace": "default"},
                        "spec": {"replicas": 2},
                        "status": {"readyReplicas": 1, "updatedReplicas": 1},
                    },
                ]
            }

        if path == k8s_policy_ns_path("local", "default", "poddisruptionbudgets"):
            return {
                "items": [
                    {
                        "metadata": {"name": "api-pdb", "namespace": "default"},
                        "spec": {
                            "minAvailable": 1,
                            "selector": {"matchLabels": {"app": "api"}},
                        },
                        "status": {
                            "currentHealthy": 1,
                            "desiredHealthy": 1,
                            "disruptionsAllowed": 0,
                        },
                    },
                    {
                        "metadata": {"name": "worker-pdb", "namespace": "default"},
                        "spec": {"maxUnavailable": 1},
                        "status": {"disruptionsAllowed": 1},
                    },
                ]
            }

        raise AssertionError(f"unexpected ops path: {path} params={params}")

    async def get_text(
        self,
        path: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> str:
        """Reject text requests because ops helpers should stay on JSON endpoints."""

        raise AssertionError(f"unexpected text path: {path} params={params}")

    async def post_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Reject write requests because ops helpers are read-only."""

        raise AssertionError(f"unexpected post path: {path} payload={payload} params={params}")
