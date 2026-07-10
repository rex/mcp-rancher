"""Curated cluster-scoped logging-pipeline set_labels tool tests."""

from __future__ import annotations

import pytest
from _logging_pipeline_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.logging_pipeline import (
    rancher_cluster_flow_set_labels,
    rancher_cluster_output_set_labels,
)

# rancher_cluster_flow_set_labels (PatchConfig substrate — cluster-scoped)
# =========================================================================


class StubClusterFlowSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for cluster_flow set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path (cluster-scoped: no namespace
    segment), then echoes the ClusterFlow payload back with the supplied
    labels applied.
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
        """Capture the merge-patch and echo a Banzai-ClusterFlow-shaped response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/clusterflows/system-cflow"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "system-cflow",
                    "labels": new_labels,
                    "annotations": {},
                },
                "spec": {
                    "loggingRef": "default",
                    "match": [{"select": {"namespaces": ["kube-system"]}}],
                    "filters": [],
                    "globalOutputRefs": ["loki-cout"],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cluster_flow_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the cluster detail path."""

    reset_rate_limit_state()
    client = StubClusterFlowSetLabelsClient()

    result = await rancher_cluster_flow_set_labels(
        cluster_flow_name="system-cflow",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path has NO namespace segment (cluster-scoped resource).
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/clusterflows/system-cflow"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through the get pipeline — curated detail returned.
    assert result.name == "system-cflow"


@pytest.mark.asyncio
async def test_rancher_cluster_flow_set_labels_emits_audit() -> None:
    """Audit record must carry operation='cluster_flow_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cluster_flow_set_labels(
            cluster_flow_name="system-cflow",
            labels={"app": "infra"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubClusterFlowSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cluster_flow_set_labels"
    assert record["operation"] == "cluster_flow_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_cluster_output_set_labels (PatchConfig substrate — cluster-scoped)
# ===========================================================================


class StubClusterOutputSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for cluster_output set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path (cluster-scoped: no namespace
    segment), then echoes the ClusterOutput payload back with the supplied
    labels applied.
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
        """Capture the merge-patch and echo a Banzai-ClusterOutput-shaped response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/clusteroutputs/loki-cout"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "loki-cout",
                    "labels": new_labels,
                    "annotations": {},
                },
                "spec": {
                    "loki": {"url": "http://loki:3100"},
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cluster_output_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the cluster detail path."""

    reset_rate_limit_state()
    client = StubClusterOutputSetLabelsClient()

    result = await rancher_cluster_output_set_labels(
        cluster_output_name="loki-cout",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path has NO namespace segment (cluster-scoped resource).
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/clusteroutputs/loki-cout"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through the get pipeline — curated detail returned.
    assert result.name == "loki-cout"


@pytest.mark.asyncio
async def test_rancher_cluster_output_set_labels_emits_audit() -> None:
    """Audit record must carry operation='cluster_output_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cluster_output_set_labels(
            cluster_output_name="loki-cout",
            labels={"app": "logging"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubClusterOutputSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cluster_output_set_labels"
    assert record["operation"] == "cluster_output_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]
