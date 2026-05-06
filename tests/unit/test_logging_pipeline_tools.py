"""Curated Banzai logging-pipeline tool tests.

Covers Output / ClusterOutput / Flow / ClusterFlow at
``logging.banzaicloud.io/v1beta1``.
"""

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.logging_pipeline import (
    rancher_cluster_flow_get,
    rancher_cluster_flow_set_annotations,
    rancher_cluster_flow_set_labels,
    rancher_cluster_flows_list,
    rancher_cluster_output_get,
    rancher_cluster_output_set_labels,
    rancher_cluster_outputs_list,
    rancher_flow_get,
    rancher_flow_set_annotations,
    rancher_flow_set_labels,
    rancher_flows_list,
    rancher_output_get,
    rancher_outputs_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for logging_pipeline tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_OUTPUT_PAYLOAD = {
    "metadata": {
        "name": "s3-out",
        "namespace": "logging",
        "annotations": {"app": "logging"},
    },
    "spec": {
        "loggingRef": "default",
        "s3": {
            "bucket": "logs-bucket",
            "region": "us-west-2",
        },
    },
}

_CLUSTER_OUTPUT_PAYLOAD = {
    "metadata": {
        "name": "loki-cout",
        "annotations": {},
    },
    "spec": {
        "loki": {"url": "http://loki:3100"},
    },
}

_FLOW_PAYLOAD = {
    "metadata": {
        "name": "app-flow",
        "namespace": "logging",
        "annotations": {"team": "platform"},
    },
    "spec": {
        "loggingRef": "default",
        "match": [
            {"select": {"labels": {"app": "demo"}}},
            {"exclude": {"labels": {"role": "system"}}},
        ],
        "filters": [
            {"parser": {"removeKeyNameField": True}},
        ],
        "localOutputRefs": ["s3-out"],
        "globalOutputRefs": ["loki-cout"],
    },
}

_CLUSTER_FLOW_PAYLOAD = {
    "metadata": {"name": "system-cflow", "annotations": {}},
    "spec": {
        "loggingRef": "default",
        "match": [{"select": {"namespaces": ["kube-system"]}}],
        "filters": [],
        "globalOutputRefs": ["loki-cout"],
    },
}


class StubLoggingPipelineClient:
    """Deterministic raw Kubernetes proxy client for logging-pipeline tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake Banzai logging CRD payloads."""

        ns_root = "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/namespaces/logging"
        cluster_root = "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1"

        if path == f"{ns_root}/outputs":
            assert params == {"limit": 5}
            return {"items": [_OUTPUT_PAYLOAD]}
        if path == f"{ns_root}/outputs/s3-out":
            assert params is None
            return _OUTPUT_PAYLOAD

        if path == f"{cluster_root}/clusteroutputs":
            assert params == {"limit": 5}
            return {"items": [_CLUSTER_OUTPUT_PAYLOAD]}
        if path == f"{cluster_root}/clusteroutputs/loki-cout":
            assert params is None
            return _CLUSTER_OUTPUT_PAYLOAD

        if path == f"{ns_root}/flows":
            assert params == {"limit": 5}
            return {"items": [_FLOW_PAYLOAD]}
        if path == f"{ns_root}/flows/app-flow":
            assert params is None
            return _FLOW_PAYLOAD

        if path == f"{cluster_root}/clusterflows":
            assert params == {"limit": 5}
            return {"items": [_CLUSTER_FLOW_PAYLOAD]}
        if path == f"{cluster_root}/clusterflows/system-cflow":
            assert params is None
            return _CLUSTER_FLOW_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")


@pytest.mark.asyncio
async def test_rancher_outputs_list_detects_output_type() -> None:
    """List should auto-detect output_type from the first non-loggingRef key."""

    result = await rancher_outputs_list(
        namespace="logging",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.output_count == 1
    [out] = result.outputs
    assert out.name == "s3-out"
    assert out.output_type == "s3"
    assert out.logging_ref == "default"


@pytest.mark.asyncio
async def test_rancher_output_get_returns_detail() -> None:
    """Detail should expose output_type, annotation_keys, full payload."""

    result = await rancher_output_get(
        namespace="logging",
        output_name="s3-out",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.name == "s3-out"
    assert result.output_type == "s3"
    assert result.annotation_keys == ["app"]
    assert result.payload == _OUTPUT_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_cluster_outputs_list_returns_summary() -> None:
    """ClusterOutput list should detect type without requiring namespace path."""

    result = await rancher_cluster_outputs_list(
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.cluster_output_count == 1
    [cout] = result.cluster_outputs
    assert cout.name == "loki-cout"
    assert cout.output_type == "loki"


@pytest.mark.asyncio
async def test_rancher_cluster_output_get_returns_detail() -> None:
    """ClusterOutput detail should expose output_type and full payload."""

    result = await rancher_cluster_output_get(
        cluster_output_name="loki-cout",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.name == "loki-cout"
    assert result.output_type == "loki"
    assert result.payload == _CLUSTER_OUTPUT_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_flows_list_counts_match_and_filter() -> None:
    """Flow list should count match clauses and filters, expose output refs."""

    result = await rancher_flows_list(
        namespace="logging",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.flow_count == 1
    [flow] = result.flows
    assert flow.name == "app-flow"
    assert flow.match_count == 2
    assert flow.filter_count == 1
    assert flow.local_output_refs == ["s3-out"]
    assert flow.global_output_refs == ["loki-cout"]


@pytest.mark.asyncio
async def test_rancher_flow_get_returns_detail() -> None:
    """Flow detail should include payload + match/filter counts."""

    result = await rancher_flow_get(
        namespace="logging",
        flow_name="app-flow",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.name == "app-flow"
    assert result.match_count == 2
    assert result.filter_count == 1
    assert result.annotation_keys == ["team"]
    assert result.payload == _FLOW_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_cluster_flows_list_returns_summary() -> None:
    """ClusterFlow list should expose match/filter counts and global output refs."""

    result = await rancher_cluster_flows_list(
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.cluster_flow_count == 1
    [cflow] = result.cluster_flows
    assert cflow.name == "system-cflow"
    assert cflow.match_count == 1
    assert cflow.filter_count == 0
    assert cflow.global_output_refs == ["loki-cout"]


@pytest.mark.asyncio
async def test_rancher_cluster_flow_get_returns_detail() -> None:
    """ClusterFlow detail should include payload."""

    result = await rancher_cluster_flow_get(
        cluster_flow_name="system-cflow",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubLoggingPipelineClient(),
    )

    assert result.name == "system-cflow"
    assert result.match_count == 1
    assert result.payload == _CLUSTER_FLOW_PAYLOAD


# rancher_flow_set_labels (PatchConfig substrate — metadata target)
# =================================================================


class StubFlowSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the flow set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the flow
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
        """Capture the merge-patch and echo a Banzai-Flow-shaped response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1"
            "/namespaces/logging/flows/app-flow"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "app-flow",
                    "namespace": "logging",
                    "labels": new_labels,
                    "annotations": {"team": "platform"},
                },
                "spec": {
                    "loggingRef": "default",
                    "match": [
                        {"select": {"labels": {"app": "demo"}}},
                    ],
                    "filters": [],
                    "localOutputRefs": ["s3-out"],
                    "globalOutputRefs": [],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_flow_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubFlowSetLabelsClient()

    result = await rancher_flow_set_labels(
        namespace="logging",
        flow_name="app-flow",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/namespaces/logging/flows/app-flow"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through the get pipeline — curated detail returned.
    assert result.name == "app-flow"
    assert result.namespace == "logging"


@pytest.mark.asyncio
async def test_rancher_flow_set_labels_emits_audit() -> None:
    """Audit record must carry operation='flow_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_flow_set_labels(
            namespace="logging",
            flow_name="app-flow",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubFlowSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_flow_set_labels"
    assert record["operation"] == "flow_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_flow_set_annotations (PatchConfig substrate — metadata target)
# ======================================================================


class StubFlowSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the flow set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the flow
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
        """Capture the merge-patch and echo a Banzai-Flow-shaped response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1"
            "/namespaces/logging/flows/app-flow"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "app-flow",
                    "namespace": "logging",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {
                    "loggingRef": "default",
                    "match": [
                        {"select": {"labels": {"app": "demo"}}},
                    ],
                    "filters": [],
                    "localOutputRefs": ["s3-out"],
                    "globalOutputRefs": [],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_flow_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubFlowSetAnnotationsClient()

    result = await rancher_flow_set_annotations(
        namespace="logging",
        flow_name="app-flow",
        annotations={"team": "platform", "env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/namespaces/logging/flows/app-flow"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_annotations = {"team": "platform", "env": "prod"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through the get pipeline — curated detail returned.
    assert result.name == "app-flow"
    assert result.namespace == "logging"


@pytest.mark.asyncio
async def test_rancher_flow_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='flow_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_flow_set_annotations(
            namespace="logging",
            flow_name="app-flow",
            annotations={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubFlowSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_flow_set_annotations"
    assert record["operation"] == "flow_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


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
