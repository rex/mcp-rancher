"""Curated Banzai logging-pipeline tool tests.

Covers Output / ClusterOutput / Flow / ClusterFlow at
``logging.banzaicloud.io/v1beta1``.
"""

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.logging_pipeline import (
    rancher_cluster_flow_get,
    rancher_cluster_flow_set_annotations,
    rancher_cluster_flow_set_labels,
    rancher_cluster_flows_list,
    rancher_cluster_output_get,
    rancher_cluster_output_set_annotations,
    rancher_cluster_output_set_labels,
    rancher_cluster_outputs_list,
    rancher_flow_delete,
    rancher_flow_get,
    rancher_flow_set_annotations,
    rancher_flow_set_labels,
    rancher_flows_list,
    rancher_output_delete,
    rancher_output_get,
    rancher_output_set_annotations,
    rancher_output_set_labels,
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


# rancher_output_set_labels (PatchConfig substrate — namespaced)
# ==============================================================


class StubOutputSetLabelsClient:
    """Stub for output set_labels tests."""

    def __init__(self) -> None:
        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r}")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)
        detail_path = (
            "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1"
            "/namespaces/logging/outputs/s3-out"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "s3-out",
                    "namespace": "logging",
                    "labels": new_labels,
                    "annotations": {"app": "logging"},
                },
                "spec": {"loggingRef": "default"},
            }
        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_output_set_labels_round_trip() -> None:
    reset_rate_limit_state()
    client = StubOutputSetLabelsClient()
    result = await rancher_output_set_labels(
        namespace="logging",
        output_name="s3-out",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/namespaces/logging/outputs/s3-out"
    )
    assert client.last_patch_payload == {
        "metadata": {"labels": {"env": "prod", "team": "platform"}}
    }
    assert result.name == "s3-out"
    assert result.namespace == "logging"


@pytest.mark.asyncio
async def test_rancher_output_set_labels_emits_audit() -> None:
    reset_rate_limit_state()
    with capture_logs() as logs:
        await rancher_output_set_labels(
            namespace="logging",
            output_name="s3-out",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubOutputSetLabelsClient(),
        )
    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_output_set_labels"
    assert record["operation"] == "output_set_labels"


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


# rancher_output_set_annotations (PatchConfig substrate — namespaced)
# ====================================================================


class StubOutputSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for output set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and namespaced detail path, then
    echoes the Output payload back with the supplied annotations applied.
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
        """Capture the merge-patch and echo a Banzai-Output-shaped response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1"
            "/namespaces/logging/outputs/s3-out"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "s3-out",
                    "namespace": "logging",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {"loggingRef": "default"},
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_output_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubOutputSetAnnotationsClient()

    result = await rancher_output_set_annotations(
        namespace="logging",
        output_name="s3-out",
        annotations={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/namespaces/logging/outputs/s3-out"
    )
    assert client.last_patch_payload == {
        "metadata": {"annotations": {"env": "prod", "team": "platform"}}
    }
    assert result.name == "s3-out"
    assert result.namespace == "logging"


@pytest.mark.asyncio
async def test_rancher_output_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='output_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_output_set_annotations(
            namespace="logging",
            output_name="s3-out",
            annotations={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubOutputSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_output_set_annotations"
    assert record["operation"] == "output_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


# =====================================================================
# rancher_output_delete end-to-end tests (D-3-output-delete)
# Block placed at END of file to avoid same-pack-pair conflicts with the
# parallel flow_delete agent in this batch.
# =====================================================================


class StubOutputDeleteClient:
    """Deterministic raw Kubernetes proxy stub for the output delete tests.

    Captures the most recent ``delete_json`` request so tests can assert
    on the namespaced detail path, then returns a Kubernetes Status
    object the way the real API server would.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for delete requests."""

        self.last_delete_path: str | None = None

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Kubernetes Status object."""

        del payload  # unused for Banzai logging Output deletes
        self.last_delete_path = path

        detail_path = (
            "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1"
            "/namespaces/logging/outputs/s3-out"
        )
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "s3-out", "kind": "outputs"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_output_delete_refuses_wrong_confirmation_before_http() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call.

    The whole point of the confirmation phrase is that an agent (or
    user) can't accidentally delete a resource by guessing the tool's
    contract. The exact phrase must be echoed back.
    """

    reset_rate_limit_state()
    client = StubOutputDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_output_delete(
            namespace="logging",
            output_name="s3-out",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call.
    assert "delete output s3-out in namespace logging" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_output_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the namespaced detail path."""

    reset_rate_limit_state()
    client = StubOutputDeleteClient()

    result = await rancher_output_delete(
        namespace="logging",
        output_name="s3-out",
        confirmation="delete output s3-out in namespace logging",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/namespaces/logging/outputs/s3-out"
    )
    assert result.deleted is True
    assert result.resource_kind == "output"
    assert result.resource_name == "s3-out"
    assert result.namespace == "logging"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete output s3-out in namespace logging"
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_outputs_list"]


@pytest.mark.asyncio
async def test_rancher_output_delete_emits_audit_on_both_paths() -> None:
    """Delete success and rejection both write audit records with operation=output_delete."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_output_delete(
            namespace="logging",
            output_name="s3-out",
            confirmation="delete output s3-out in namespace logging",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubOutputDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["tool_name"] == "rancher_output_delete"
    assert success_audits[0]["operation"] == "output_delete"
    assert success_audits[0]["plane"] == "steve"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_output_delete(
            namespace="logging",
            output_name="s3-out",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubOutputDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["tool_name"] == "rancher_output_delete"
    assert reject_audits[0]["operation"] == "output_delete"
    assert reject_audits[0]["outcome"] == "error"
    # Audit captures the rejection reason but never the wrong phrase value.
    assert "bad" not in reject_audits[0].get("arg_keys", [])


# =====================================================================
# rancher_flow_delete tests (D-3-flow-delete)
# =====================================================================


class StubFlowDeleteClient:
    """Delete-capable raw Kubernetes proxy stub for the flow delete tests.

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

        del payload  # unused for k8s flow deletes
        self.last_delete_path = path

        detail_path = (
            "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1"
            "/namespaces/logging/flows/app-flow"
        )
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "app-flow", "kind": "flows"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_flow_delete_refuses_wrong_confirmation_before_http() -> None:
    """Wrong confirmation phrase raises RancherCapabilityError before any HTTP call."""

    reset_rate_limit_state()
    client = StubFlowDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_flow_delete(
            namespace="logging",
            flow_name="app-flow",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call.
    assert "delete flow app-flow in namespace logging" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_flow_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubFlowDeleteClient()

    result = await rancher_flow_delete(
        namespace="logging",
        flow_name="app-flow",
        confirmation="delete flow app-flow in namespace logging",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/namespaces/logging/flows/app-flow"
    )
    assert result.deleted is True
    assert result.resource_kind == "flow"
    assert result.resource_name == "app-flow"
    assert result.namespace == "logging"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete flow app-flow in namespace logging"
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_flows_list"]


@pytest.mark.asyncio
async def test_rancher_flow_delete_emits_audit_on_both_paths() -> None:
    """Delete success and rejection both write audit records with operation=flow_delete."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_flow_delete(
            namespace="logging",
            flow_name="app-flow",
            confirmation="delete flow app-flow in namespace logging",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubFlowDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["tool_name"] == "rancher_flow_delete"
    assert success_audits[0]["operation"] == "flow_delete"
    assert success_audits[0]["plane"] == "steve"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_flow_delete(
            namespace="logging",
            flow_name="app-flow",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubFlowDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "flow_delete"
    assert reject_audits[0]["outcome"] == "error"
