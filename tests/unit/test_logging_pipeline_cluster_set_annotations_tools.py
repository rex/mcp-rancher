"""Curated cluster-scoped logging-pipeline set_annotations tool tests."""

from __future__ import annotations

import pytest
from _logging_pipeline_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.logging_pipeline import (
    rancher_cluster_flow_set_annotations,
    rancher_cluster_output_set_annotations,
)

# rancher_cluster_flow_set_annotations (PatchConfig substrate — cluster-scoped)
# =============================================================================


class StubClusterFlowSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for cluster_flow set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path (cluster-scoped: no namespace
    segment), then echoes the ClusterFlow payload back with the supplied
    annotations applied.
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
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "system-cflow",
                    "labels": {},
                    "annotations": new_annotations,
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
async def test_rancher_cluster_flow_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the cluster detail path."""

    reset_rate_limit_state()
    client = StubClusterFlowSetAnnotationsClient()

    result = await rancher_cluster_flow_set_annotations(
        cluster_flow_name="system-cflow",
        annotations={"owner": "platform", "env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path has NO namespace segment (cluster-scoped resource).
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/clusterflows/system-cflow"
    )
    # Body is exactly the narrow patch — annotations nested under target_path=metadata.
    expected_annotations = {"owner": "platform", "env": "prod"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through the get pipeline — curated detail returned.
    assert result.name == "system-cflow"


@pytest.mark.asyncio
async def test_rancher_cluster_flow_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='cluster_flow_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cluster_flow_set_annotations(
            cluster_flow_name="system-cflow",
            annotations={"app": "infra"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubClusterFlowSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cluster_flow_set_annotations"
    assert record["operation"] == "cluster_flow_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


# rancher_cluster_output_set_annotations (cluster-scoped)
# ========================================================


class StubClusterOutputSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for cluster_output set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path (cluster-scoped: no namespace
    segment), then echoes the ClusterOutput payload back with the supplied
    annotations applied.
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
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "loki-cout",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {
                    "loki": {"url": "http://loki:3100"},
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cluster_output_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the cluster detail path."""

    reset_rate_limit_state()
    client = StubClusterOutputSetAnnotationsClient()

    result = await rancher_cluster_output_set_annotations(
        cluster_output_name="loki-cout",
        annotations={"env": "prod", "team": "platform"},
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
    expected_annotations = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through the get pipeline — curated detail returned.
    assert result.name == "loki-cout"


@pytest.mark.asyncio
async def test_rancher_cluster_output_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='cluster_output_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cluster_output_set_annotations(
            cluster_output_name="loki-cout",
            annotations={"app": "logging"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubClusterOutputSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cluster_output_set_annotations"
    assert record["operation"] == "cluster_output_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
