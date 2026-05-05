"""Curated disruption-management tool tests."""

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.disruption import (
    rancher_pod_disruption_budget_delete,
    rancher_pod_disruption_budget_get,
    rancher_pod_disruption_budget_set_annotations,
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


# rancher_pod_disruption_budget_set_annotations tests
# =====================================================================


class StubPdbSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the PDB set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the PDB
    payload back with the supplied annotations applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_annotations tests don't need GET; raise to surface accidental usage."""

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
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-pdb",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": new_annotations,
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
async def test_rancher_pod_disruption_budget_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubPdbSetAnnotationsClient()

    result = await rancher_pod_disruption_budget_set_annotations(
        namespace="demo",
        budget_name="demo-pdb",
        annotations={"team": "platform", "env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/policy/v1/namespaces/demo/poddisruptionbudgets/demo-pdb"
    )
    # Body is exactly the narrow patch — annotations nested under target_path=metadata.
    expected_annotations = {"team": "platform", "env": "prod"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-pdb"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_pod_disruption_budget_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='pod_disruption_budget_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_pod_disruption_budget_set_annotations(
            namespace="demo",
            budget_name="demo-pdb",
            annotations={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPdbSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_pod_disruption_budget_set_annotations"
    assert record["operation"] == "pod_disruption_budget_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


# rancher_pod_disruption_budget_delete tests
# =====================================================================


class StubPdbDeleteClient:
    """Delete-capable raw Kubernetes proxy stub for the PDB delete tests.

    Captures the most recent ``delete_json`` request path so tests can
    assert no HTTP call happened on a bad confirmation, then returns a
    Kubernetes Status object on a successful DELETE.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for delete requests."""

        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The delete tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Kubernetes Status object."""

        del payload  # unused for k8s PDB deletes
        self.last_delete_path = path

        detail_path = (
            "/k8s/clusters/local/apis/policy/v1/namespaces/demo/poddisruptionbudgets/demo-pdb"
        )
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-pdb", "kind": "poddisruptionbudgets"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_pod_disruption_budget_delete_refuses_wrong_confirmation() -> None:
    """Wrong confirmation phrase raises RancherCapabilityError before any HTTP call."""

    reset_rate_limit_state()
    client = StubPdbDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_pod_disruption_budget_delete(
            namespace="demo",
            budget_name="demo-pdb",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete pod_disruption_budget demo-pdb in namespace demo" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_pod_disruption_budget_delete_with_correct_phrase_succeeds() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubPdbDeleteClient()

    result = await rancher_pod_disruption_budget_delete(
        namespace="demo",
        budget_name="demo-pdb",
        confirmation="delete pod_disruption_budget demo-pdb in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert (
        client.last_delete_path
        == "/k8s/clusters/local/apis/policy/v1/namespaces/demo/poddisruptionbudgets/demo-pdb"
    )
    assert result.deleted is True
    assert result.resource_kind == "pod_disruption_budget"
    assert result.resource_name == "demo-pdb"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == (
        "delete pod_disruption_budget demo-pdb in namespace demo"
    )
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_pod_disruption_budgets_list"]


@pytest.mark.asyncio
async def test_rancher_pod_disruption_budget_delete_emits_audit_with_outcome() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_pod_disruption_budget_delete(
            namespace="demo",
            budget_name="demo-pdb",
            confirmation="delete pod_disruption_budget demo-pdb in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPdbDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "pod_disruption_budget_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_pod_disruption_budget_delete(
            namespace="demo",
            budget_name="demo-pdb",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPdbDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "pod_disruption_budget_delete"
    assert reject_audits[0]["outcome"] == "error"
