"""Curated DaemonSet tool tests (set_labels + set_annotations)."""

from __future__ import annotations

import pytest
from _workloads_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.workloads import (
    rancher_daemonset_set_annotations,
    rancher_daemonset_set_labels,
)

# =====================================================================
# rancher_daemonset_set_labels (single-patch virgin case)
# =====================================================================


class StubDaemonSetSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the daemonset set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the daemonset
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
        """Capture the merge-patch and echo a Kubernetes-shaped daemonset response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/venue-local/apis/apps/v1/namespaces/kube-system/daemonsets/kindnet"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "kindnet",
                    "namespace": "kube-system",
                    "labels": new_labels,
                    "generation": 2,
                },
                "spec": {
                    "updateStrategy": {"type": "RollingUpdate"},
                    "selector": {"matchLabels": {"app": "kindnet"}},
                    "template": {
                        "spec": {
                            "serviceAccountName": "kindnet",
                            "containers": [
                                {
                                    "name": "kindnet-cni",
                                    "image": "docker.io/kindest/kindnetd:v20240202-8f1494ea",
                                }
                            ],
                        }
                    },
                },
                "status": {
                    "desiredNumberScheduled": 2,
                    "currentNumberScheduled": 2,
                    "numberReady": 2,
                    "numberAvailable": 2,
                    "updatedNumberScheduled": 2,
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_daemonset_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubDaemonSetSetLabelsClient()

    result = await rancher_daemonset_set_labels(
        namespace="kube-system",
        daemonset_name="kindnet",
        labels={"env": "prod", "team": "platform"},
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/kube-system/daemonsets/kindnet"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "kindnet"
    assert result.namespace == "kube-system"


@pytest.mark.asyncio
async def test_rancher_daemonset_set_labels_emits_audit() -> None:
    """Audit record must carry operation='daemonset_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_daemonset_set_labels(
            namespace="kube-system",
            daemonset_name="kindnet",
            labels={"app": "kindnet"},
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubDaemonSetSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_daemonset_set_labels"
    assert record["operation"] == "daemonset_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# =====================================================================
# rancher_daemonset_set_annotations (multi-patch — 2nd entry alongside set_labels)
# =====================================================================


class StubDaemonSetSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the daemonset set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the daemonset
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
        """Capture the merge-patch and echo a Kubernetes-shaped daemonset response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/venue-local/apis/apps/v1/namespaces/kube-system/daemonsets/kindnet"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "kindnet",
                    "namespace": "kube-system",
                    "annotations": new_annotations,
                    "generation": 2,
                },
                "spec": {
                    "updateStrategy": {"type": "RollingUpdate"},
                    "selector": {"matchLabels": {"app": "kindnet"}},
                    "template": {
                        "spec": {
                            "serviceAccountName": "kindnet",
                            "containers": [
                                {
                                    "name": "kindnet-cni",
                                    "image": "docker.io/kindest/kindnetd:v20240202-8f1494ea",
                                }
                            ],
                        }
                    },
                },
                "status": {
                    "desiredNumberScheduled": 2,
                    "currentNumberScheduled": 2,
                    "numberReady": 2,
                    "numberAvailable": 2,
                    "updatedNumberScheduled": 2,
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_daemonset_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubDaemonSetSetAnnotationsClient()

    result = await rancher_daemonset_set_annotations(
        namespace="kube-system",
        daemonset_name="kindnet",
        annotations={"owner": "platform", "env": "prod"},
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/kube-system/daemonsets/kindnet"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_annotations = {"owner": "platform", "env": "prod"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "kindnet"
    assert result.namespace == "kube-system"


@pytest.mark.asyncio
async def test_rancher_daemonset_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='daemonset_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_daemonset_set_annotations(
            namespace="kube-system",
            daemonset_name="kindnet",
            annotations={"app": "kindnet"},
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubDaemonSetSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_daemonset_set_annotations"
    assert record["operation"] == "daemonset_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
