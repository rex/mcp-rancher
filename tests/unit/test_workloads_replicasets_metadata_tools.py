"""Curated ReplicaSet tool tests (set_labels + set_annotations)."""

from __future__ import annotations

import pytest
from _workloads_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.workloads import (
    rancher_replica_set_set_annotations,
    rancher_replica_set_set_labels,
)

# =====================================================================
# rancher_replica_set_set_labels (single-patch virgin case)
# =====================================================================


class StubReplicaSetSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the replica_set set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the replicaset
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
        """Capture the merge-patch and echo a Kubernetes-shaped replicaset response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/replicasets/nginx-rs"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "nginx-rs",
                    "namespace": "apps",
                    "labels": new_labels,
                },
                "spec": {
                    "replicas": 3,
                    "selector": {"matchLabels": {"app": "nginx"}},
                    "template": {
                        "spec": {
                            "containers": [{"name": "nginx", "image": "nginx:1.25"}],
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

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_replica_set_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubReplicaSetSetLabelsClient()

    result = await rancher_replica_set_set_labels(
        namespace="apps",
        replica_set_name="nginx-rs",
        labels={"env": "prod", "team": "platform"},
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/replicasets/nginx-rs"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "nginx-rs"
    assert result.namespace == "apps"


@pytest.mark.asyncio
async def test_rancher_replica_set_set_labels_emits_audit() -> None:
    """Audit record must carry operation='replicaset_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_replica_set_set_labels(
            namespace="apps",
            replica_set_name="nginx-rs",
            labels={"app": "web"},
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubReplicaSetSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_replica_set_set_labels"
    assert record["operation"] == "replicaset_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_replica_set_set_annotations (multi-patch: set_labels + set_annotations)
# =====================================================================


class StubReplicaSetSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the replica_set set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the replicaset
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
        """Capture the merge-patch and echo a Kubernetes-shaped replicaset response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/replicasets/nginx-rs"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "nginx-rs",
                    "namespace": "apps",
                    "annotations": new_annotations,
                },
                "spec": {
                    "replicas": 3,
                    "selector": {"matchLabels": {"app": "nginx"}},
                    "template": {
                        "spec": {
                            "containers": [{"name": "nginx", "image": "nginx:1.25"}],
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

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_replica_set_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubReplicaSetSetAnnotationsClient()

    result = await rancher_replica_set_set_annotations(
        namespace="apps",
        replica_set_name="nginx-rs",
        annotations={"owner": "platform-team", "managed-by": "argocd"},
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/replicasets/nginx-rs"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_annotations = {"owner": "platform-team", "managed-by": "argocd"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "nginx-rs"
    assert result.namespace == "apps"


@pytest.mark.asyncio
async def test_rancher_replica_set_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='replica_set_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_replica_set_set_annotations(
            namespace="apps",
            replica_set_name="nginx-rs",
            annotations={"env": "staging"},
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubReplicaSetSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_replica_set_set_annotations"
    assert record["operation"] == "replica_set_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
