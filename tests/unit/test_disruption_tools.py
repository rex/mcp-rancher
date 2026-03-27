"""Curated disruption-management tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.disruption import (
    rancher_pod_disruption_budget_get,
    rancher_pod_disruption_budgets_list,
)


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


@pytest.mark.asyncio
async def test_rancher_pod_disruption_budgets_list_returns_typed_summaries() -> None:
    """Curated PDB list should expose typed disruption summaries."""

    result = await rancher_pod_disruption_budgets_list(
        namespace="storage-validation",
        cluster_id="venue-local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.cluster_id == "venue-local"
    assert result.namespace == "storage-validation"
    assert result.budget_count == 1
    assert result.pod_disruption_budgets[0].id == "storage-validation/demo-consumer-pdb"
    assert result.pod_disruption_budgets[0].disruption_allowed is False


@pytest.mark.asyncio
async def test_rancher_pod_disruption_budget_get_returns_typed_detail() -> None:
    """Curated PDB detail should expose selector and condition detail."""

    result = await rancher_pod_disruption_budget_get(
        namespace="storage-validation",
        budget_name="demo-consumer-pdb",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.id == "storage-validation/demo-consumer-pdb"
    assert result.selector_match_labels == {"app": "demo-consumer"}
    assert result.conditions[0].reason == "InsufficientPods"
