"""Curated PodDisruptionBudget set_labels / set_annotations tool tests."""

from __future__ import annotations

import pytest
from _disruption_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.disruption import (
    rancher_pod_disruption_budget_set_annotations,
    rancher_pod_disruption_budget_set_labels,
)

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
