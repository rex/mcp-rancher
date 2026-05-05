"""Curated disruption-management tool tests."""

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.disruption import (
    rancher_pod_disruption_budget_get,
    rancher_pod_disruption_budget_set_labels,
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
    assert result.pod_disruption_budgets[0].min_available == "1"
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
    assert result.min_available == "1"
    assert result.selector_match_labels == {"app": "demo-consumer"}
    assert result.conditions[0].reason == "InsufficientPods"


# rancher_pod_disruption_budget_set_labels tests
# =====================================================================


class StubPdbSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the PDB set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the PDB
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
        """Capture the merge-patch and echo a Kubernetes-shaped PDB response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/policy/v1/namespaces/demo/poddisruptionbudgets/demo-pdb"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-pdb",
                    "namespace": "demo",
                    "labels": new_labels,
                    "annotations": {},
                },
                "spec": {
                    "minAvailable": 1,
                    "selector": {"matchLabels": {"app": "demo"}},
                },
                "status": {
                    "currentHealthy": 2,
                    "desiredHealthy": 1,
                    "expectedPods": 2,
                    "disruptionsAllowed": 1,
                    "conditions": [
                        {
                            "type": "DisruptionAllowed",
                            "status": "True",
                            "reason": "SufficientPods",
                            "message": "",
                        }
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_pod_disruption_budget_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubPdbSetLabelsClient()

    result = await rancher_pod_disruption_budget_set_labels(
        namespace="demo",
        budget_name="demo-pdb",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/policy/v1/namespaces/demo/poddisruptionbudgets/demo-pdb"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-pdb"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_pod_disruption_budget_set_labels_emits_audit() -> None:
    """Audit record must carry operation='pod_disruption_budget_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_pod_disruption_budget_set_labels(
            namespace="demo",
            budget_name="demo-pdb",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPdbSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_pod_disruption_budget_set_labels"
    assert record["operation"] == "pod_disruption_budget_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]
