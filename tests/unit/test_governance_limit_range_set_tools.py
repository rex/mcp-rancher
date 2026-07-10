"""Curated LimitRange metadata-setter tool tests (set_labels, set_annotations)."""

from __future__ import annotations

import pytest
from _governance_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.governance import (
    rancher_limit_range_set_annotations,
    rancher_limit_range_set_labels,
)


class StubLimitRangeSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the LimitRange set_labels tests.

    Captures the most recent ``patch_json`` request so tests can assert on
    the merge-patch body and path, then echoes the LimitRange payload back
    with the supplied labels applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped LimitRange response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/local/api/v1/namespaces/demo/limitranges/demo-limits"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-limits",
                    "namespace": "demo",
                    "labels": new_labels,
                    "annotations": {},
                },
                "spec": {
                    "limits": [
                        {"type": "Container", "default": {"cpu": "200m"}},
                        {"type": "Pod", "max": {"cpu": "4"}},
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_limit_range_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubLimitRangeSetLabelsClient()

    result = await rancher_limit_range_set_labels(
        namespace="demo",
        limit_range_name="demo-limits",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path (core/v1), not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/api/v1/namespaces/demo/limitranges/demo-limits"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-limits"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_limit_range_set_labels_emits_audit() -> None:
    """Audit record must carry operation='limit_range_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_limit_range_set_labels(
            namespace="demo",
            limit_range_name="demo-limits",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubLimitRangeSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_limit_range_set_labels"
    assert record["operation"] == "limit_range_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


class StubLimitRangeSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the LimitRange set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can assert on
    the merge-patch body and path, then echoes the LimitRange payload back
    with the supplied annotations applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped LimitRange response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/local/api/v1/namespaces/demo/limitranges/demo-limits"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-limits",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {
                    "limits": [
                        {"type": "Container", "default": {"cpu": "200m"}},
                        {"type": "Pod", "max": {"cpu": "4"}},
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_limit_range_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubLimitRangeSetAnnotationsClient()

    result = await rancher_limit_range_set_annotations(
        namespace="demo",
        limit_range_name="demo-limits",
        annotations={"owner": "platform", "tier": "production"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path (core/v1), not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/api/v1/namespaces/demo/limitranges/demo-limits"
    )
    # Body is exactly the narrow patch — annotations nested under target_path=metadata.
    expected_annotations = {"owner": "platform", "tier": "production"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-limits"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_limit_range_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='limit_range_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_limit_range_set_annotations(
            namespace="demo",
            limit_range_name="demo-limits",
            annotations={"env": "staging"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubLimitRangeSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_limit_range_set_annotations"
    assert record["operation"] == "limit_range_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
