"""Shared setup for the curated disruption-management tool test suites.

Extracted from ``test_disruption_tools.py`` when it was split by operation
family to stay under the architecture line limit. ``build_settings`` and the
shared read stub are consumed across the disruption test modules;
operation-specific stubs stay with the tests that use them.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


def build_settings() -> AppSettings:
    """Create deterministic settings for curated disruption tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubRawK8sClient:
    """Deterministic raw Kubernetes proxy client for curated PDB tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake raw Kubernetes PDB payloads."""

        collection_path = (
            "/k8s/clusters/venue-local/apis/policy/v1/namespaces/"
            "storage-validation/poddisruptionbudgets"
        )
        if path == collection_path:
            assert params == {"limit": 5}
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "demo-consumer-pdb",
                            "namespace": "storage-validation",
                            "annotations": {
                                "kubectl.kubernetes.io/last-applied-configuration": "{}",
                            },
                        },
                        "spec": {
                            "minAvailable": 1,
                            "selector": {
                                "matchLabels": {
                                    "app": "demo-consumer",
                                }
                            },
                        },
                        "status": {
                            "currentHealthy": 1,
                            "desiredHealthy": 1,
                            "expectedPods": 1,
                            "disruptionsAllowed": 0,
                            "conditions": [
                                {
                                    "type": "DisruptionAllowed",
                                    "status": "False",
                                    "reason": "InsufficientPods",
                                    "message": "",
                                }
                            ],
                        },
                    }
                ]
            }
        if path == f"{collection_path}/demo-consumer-pdb":
            assert params is None
            return {
                "metadata": {
                    "name": "demo-consumer-pdb",
                    "namespace": "storage-validation",
                    "annotations": {
                        "kubectl.kubernetes.io/last-applied-configuration": "{}",
                    },
                },
                "spec": {
                    "minAvailable": 1,
                    "selector": {
                        "matchLabels": {
                            "app": "demo-consumer",
                        }
                    },
                },
                "status": {
                    "currentHealthy": 1,
                    "desiredHealthy": 1,
                    "expectedPods": 1,
                    "disruptionsAllowed": 0,
                    "conditions": [
                        {
                            "type": "DisruptionAllowed",
                            "status": "False",
                            "reason": "InsufficientPods",
                            "message": "",
                        }
                    ],
                },
            }
        raise AssertionError(f"unexpected raw K8s path: {path}")
