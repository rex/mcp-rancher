"""Shared setup for the curated project/namespace tool test suites.

Extracted from ``test_projects_namespaces_tools.py`` when it was split by
resource/operation to stay under the architecture line limit.
``build_settings`` and the shared read stubs ``StubManagementClient`` and
``StubSteveClient`` are consumed by the project/namespace list/get test
modules; operation-specific stubs stay with the tests that use them.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


def build_settings() -> AppSettings:
    """Create deterministic settings for curated project/namespace tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubManagementClient:
    """Deterministic management client for curated project tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake project payloads."""

        if path == "/v3/projects":
            assert params == {
                "clusterId": "venue-local",
                "state": "active",
                "limit": 2,
                "sort": "name",
                "reverse": True,
            }
            return {
                "data": [
                    {
                        "id": "venue-local:p-kzmtj",
                        "name": "System",
                        "clusterId": "venue-local",
                        "state": "active",
                        "description": "System project created for the cluster",
                        "enableProjectMonitoring": False,
                        "labels": {
                            "authz.management.cattle.io/system-project": "true",
                            "cattle.io/creator": "norman",
                        },
                        "conditions": [
                            {"type": "BackingNamespaceCreated", "status": "True"},
                            {"type": "CreatorMadeOwner", "status": "True"},
                        ],
                    }
                ]
            }
        if path == "/v3/projects/venue-local:p-kzmtj":
            assert params is None
            return {
                "id": "venue-local:p-kzmtj",
                "name": "System",
                "clusterId": "venue-local",
                "state": "active",
                "description": "System project created for the cluster",
                "enableProjectMonitoring": False,
                "namespaceId": None,
                "podSecurityPolicyTemplateId": "",
                "transitioning": "no",
                "transitioningMessage": "",
                "actions": {
                    "exportYaml": "https://rancher.work.example.com/v3/projects/venue-local:p-kzmtj?action=exportYaml",
                },
                "links": {
                    "self": "https://rancher.work.example.com/v3/projects/venue-local:p-kzmtj",
                    "pods": "https://rancher.work.example.com/v3/projects/venue-local:p-kzmtj/pods",
                },
                "labels": {
                    "authz.management.cattle.io/system-project": "true",
                    "cattle.io/creator": "norman",
                },
                "conditions": [
                    {"type": "BackingNamespaceCreated", "status": "True"},
                    {"type": "CreatorMadeOwner", "status": "True"},
                    {"type": "SystemNamespacesAssigned", "status": "True"},
                ],
            }
        raise AssertionError(f"unexpected management path: {path}")


class StubSteveClient:
    """Deterministic Steve client for curated namespace tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake namespace payloads."""

        if path == "/namespaces":
            assert params == {
                "limit": 2,
                "labelSelector": "team=ops,field.cattle.io/projectId=p-kzmtj",
            }
            return {
                "data": [
                    {
                        "id": "cattle-system",
                        "metadata": {
                            "name": "cattle-system",
                            "annotations": {
                                "field.cattle.io/projectId": "venue-local:p-kzmtj",
                                "cattle.io/status": (
                                    '{"Conditions":[{"Type":"ResourceQuotaInit","Status":"True",'
                                    '"Message":""},{"Type":"InitialRolesPopulated","Status":"True",'
                                    '"Message":""}]}'
                                ),
                            },
                            "labels": {
                                "field.cattle.io/projectId": "p-kzmtj",
                                "kubernetes.io/metadata.name": "cattle-system",
                            },
                            "finalizers": ["controller.cattle.io/namespace-auth"],
                            "state": {
                                "name": "active",
                                "message": "",
                                "error": False,
                            },
                        },
                        "status": {
                            "phase": "Active",
                        },
                    }
                ]
            }
        if path == "/namespaces/cattle-system":
            assert params is None
            return {
                "id": "cattle-system",
                "links": {
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/namespaces/cattle-system",
                    "view": "https://rancher.work.example.com/k8s/clusters/venue-local/api/v1/namespaces/cattle-system",
                },
                "metadata": {
                    "name": "cattle-system",
                    "annotations": {
                        "field.cattle.io/projectId": "venue-local:p-kzmtj",
                        "cattle.io/status": (
                            '{"Conditions":[{"Type":"ResourceQuotaInit","Status":"True","Message":""},'
                            '{"Type":"InitialRolesPopulated","Status":"True","Message":""}]}'
                        ),
                    },
                    "labels": {
                        "field.cattle.io/projectId": "p-kzmtj",
                        "kubernetes.io/metadata.name": "cattle-system",
                    },
                    "finalizers": ["controller.cattle.io/namespace-auth"],
                    "state": {
                        "name": "active",
                        "message": "",
                        "error": False,
                    },
                },
                "status": {
                    "phase": "Active",
                },
            }
        raise AssertionError(f"unexpected Steve path: {path}")
