"""Curated namespace tool tests (set_annotations)."""

from __future__ import annotations

import pytest
from _projects_namespaces_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.projects_namespaces import rancher_namespace_set_annotations

# rancher_namespace_set_annotations (PatchConfig substrate — Steve transport)
# ===========================================================================


class StubNamespaceSetAnnotationsClient:
    """Patch-capable Steve stub for the namespace set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can assert on
    the merge-patch body and path, then echoes a namespace payload with
    the supplied annotations applied.
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
        """Capture the merge-patch and echo a Steve-shaped namespace response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        if path == "/namespaces/cattle-system":
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "id": "cattle-system",
                "links": {
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/namespaces/cattle-system",
                    "view": "https://rancher.work.example.com/k8s/clusters/venue-local/api/v1/namespaces/cattle-system",
                },
                "metadata": {
                    "name": "cattle-system",
                    "annotations": new_annotations,
                    "labels": {
                        "kubernetes.io/metadata.name": "cattle-system",
                    },
                    "finalizers": ["controller.cattle.io/namespace-auth"],
                    "state": {"name": "active", "message": "", "error": False},
                },
                "status": {"phase": "Active"},
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_namespace_set_annotations_round_trip() -> None:
    """PATCH body must be {metadata: {annotations: <dict>}} at the Steve detail path."""

    reset_rate_limit_state()
    client = StubNamespaceSetAnnotationsClient()

    result = await rancher_namespace_set_annotations(
        namespace="cattle-system",
        annotations={"example.io/owner": "platform-team", "example.io/env": "prod"},
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped resource: path has NO extra namespace segment.
    assert client.last_patch_path == "/namespaces/cattle-system"
    # Body is exactly the narrow merge-patch.
    assert client.last_patch_payload == {
        "metadata": {"annotations": {"example.io/owner": "platform-team", "example.io/env": "prod"}}
    }
    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "cattle-system"


@pytest.mark.asyncio
async def test_rancher_namespace_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='namespace_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_namespace_set_annotations(
            namespace="cattle-system",
            annotations={"example.io/managed-by": "fleet"},
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubNamespaceSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_namespace_set_annotations"
    assert record["operation"] == "namespace_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
