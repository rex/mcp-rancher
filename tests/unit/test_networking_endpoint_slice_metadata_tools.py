"""Curated endpoint slice tool tests (set_labels + set_annotations)."""

from __future__ import annotations

import pytest
from _networking_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.networking import (
    rancher_endpoint_slice_set_annotations,
    rancher_endpoint_slice_set_labels,
)

# =====================================================================
# rancher_endpoint_slice_set_labels (PatchConfig substrate)
# =====================================================================


class StubEndpointSliceSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the endpoint_slice set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the endpoint
    slice payload back with the supplied labels applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped endpoint slice response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/discovery.k8s.io/v1/namespaces/demo/endpointslices/demo-slice"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-slice",
                    "namespace": "demo",
                    "labels": new_labels,
                    "annotations": {},
                },
                "addressType": "IPv4",
                "ports": [{"name": "http", "port": 80}, {"name": "https", "port": 443}],
                "endpoints": [
                    {"addresses": ["10.42.0.1"], "conditions": {"ready": True}},
                    {"addresses": ["10.42.0.2"], "conditions": {"ready": False}},
                    {"addresses": ["10.42.0.3"], "conditions": {"ready": True}},
                ],
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_endpoint_slice_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubEndpointSliceSetLabelsClient()

    result = await rancher_endpoint_slice_set_labels(
        namespace="demo",
        endpoint_slice_name="demo-slice",
        labels={"env": "prod", "team": "networking"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/discovery.k8s.io/v1/namespaces/demo/endpointslices/demo-slice"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "networking"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-slice"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_endpoint_slice_set_labels_emits_audit() -> None:
    """Audit record must carry operation='endpoint_slice_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_endpoint_slice_set_labels(
            namespace="demo",
            endpoint_slice_name="demo-slice",
            labels={"app": "backend"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubEndpointSliceSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_endpoint_slice_set_labels"
    assert record["operation"] == "endpoint_slice_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_endpoint_slice_set_annotations (multi-patch substrate proof)
# =====================================================================


class StubEndpointSliceSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the endpoint_slice set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the endpoint
    slice payload back with the supplied annotations applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped endpoint slice response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/discovery.k8s.io/v1/namespaces/demo/endpointslices/demo-slice"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-slice",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "addressType": "IPv4",
                "ports": [{"name": "http", "port": 80}],
                "endpoints": [
                    {"addresses": ["10.42.0.1"], "conditions": {"ready": True}},
                ],
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_endpoint_slice_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubEndpointSliceSetAnnotationsClient()

    result = await rancher_endpoint_slice_set_annotations(
        namespace="demo",
        endpoint_slice_name="demo-slice",
        annotations={"kubectl.kubernetes.io/last-applied-configuration": "{}"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/discovery.k8s.io/v1/namespaces/demo/endpointslices/demo-slice"
    )
    expected_annotations = {"kubectl.kubernetes.io/last-applied-configuration": "{}"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    assert result.name == "demo-slice"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_endpoint_slice_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='endpoint_slice_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_endpoint_slice_set_annotations(
            namespace="demo",
            endpoint_slice_name="demo-slice",
            annotations={"app.kubernetes.io/version": "v1"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubEndpointSliceSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_endpoint_slice_set_annotations"
    assert record["operation"] == "endpoint_slice_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
