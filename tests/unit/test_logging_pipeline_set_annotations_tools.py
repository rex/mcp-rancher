"""Curated logging-pipeline set_annotations tool tests (namespaced Flow + Output)."""

from __future__ import annotations

import pytest
from _logging_pipeline_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.logging_pipeline import (
    rancher_flow_set_annotations,
    rancher_output_set_annotations,
)

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
