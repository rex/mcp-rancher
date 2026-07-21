"""Curated PersistentVolumeClaim tool tests (list/get + delete + set_size)."""

from __future__ import annotations

import pytest
from _storage_support import StubRawK8sClient, build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.storage import (
    rancher_persistent_volume_claim_delete,
    rancher_persistent_volume_claim_get,
    rancher_persistent_volume_claim_set_size,
    rancher_persistent_volume_claims_list,
)


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claims_list_returns_typed_summaries() -> None:
    """Curated PVC list should expose typed claim summaries."""

    result = await rancher_persistent_volume_claims_list(
        namespace="storage-validation",
        cluster_id="venue-local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.namespace == "storage-validation"
    assert result.claim_count == 1
    assert result.persistent_volume_claims[0].id == "storage-validation/demo-claim"
    assert result.persistent_volume_claims[0].volume_name == "pvc-demo"


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_get_returns_typed_detail() -> None:
    """Curated PVC detail should expose selected-node and finalizer detail."""

    result = await rancher_persistent_volume_claim_get(
        namespace="storage-validation",
        claim_name="demo-claim",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.id == "storage-validation/demo-claim"
    assert result.selected_node == "venue-worker-1"
    assert result.finalizers == ["kubernetes.io/pvc-protection"]


# =====================================================================
# PersistentVolumeClaim delete
# =====================================================================


class StubPersistentVolumeClaimDeleteClient:
    """Delete-capable stub for PersistentVolumeClaim delete.

    Captures the most recent ``delete_json`` call for assertion.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """delete tests do not call GET."""

        raise AssertionError(f"unexpected get on {path!r}")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Kubernetes Status object."""

        del payload  # unused for k8s pvc deletes
        self.last_delete_path = path
        return {"apiVersion": "v1", "kind": "Status", "status": "Success"}


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_delete_refuses_wrong_confirmation() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubPersistentVolumeClaimDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_persistent_volume_claim_delete(
            namespace="storage-validation",
            claim_name="demo-claim",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete persistent_volume_claim demo-claim in namespace storage-validation" in str(
        excinfo.value
    )
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_delete_routes_to_delete_json() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubPersistentVolumeClaimDeleteClient()

    result = await rancher_persistent_volume_claim_delete(
        namespace="storage-validation",
        claim_name="demo-claim",
        confirmation="delete persistent_volume_claim demo-claim in namespace storage-validation",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/api/v1/namespaces/storage-validation/persistentvolumeclaims/demo-claim"
    )
    assert result.deleted is True
    assert result.resource_kind == "persistent_volume_claim"
    assert result.resource_name == "demo-claim"
    assert result.namespace == "storage-validation"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == (
        "delete persistent_volume_claim demo-claim in namespace storage-validation"
    )
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_persistent_volume_claims_list"]


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_delete_emits_audit() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    _good_phrase = "delete persistent_volume_claim demo-claim in namespace storage-validation"
    with capture_logs() as success_logs:
        await rancher_persistent_volume_claim_delete(
            namespace="storage-validation",
            claim_name="demo-claim",
            confirmation=_good_phrase,
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPersistentVolumeClaimDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "persistent_volume_claim_delete"
    assert success_audits[0]["outcome"] == "success"

    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_persistent_volume_claim_delete(
            namespace="storage-validation",
            claim_name="demo-claim",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPersistentVolumeClaimDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "persistent_volume_claim_delete"
    assert reject_audits[0]["outcome"] == "error"


# =====================================================================
# PersistentVolumeClaim set_size (patch)
# =====================================================================

_PATCHED_PVC_RESIZED_PAYLOAD: dict[str, object] = {
    "metadata": {
        "name": "demo-claim",
        "namespace": "storage-validation",
        "annotations": {
            "volume.kubernetes.io/selected-node": "venue-worker-1",
        },
        "finalizers": ["kubernetes.io/pvc-protection"],
    },
    "spec": {
        "storageClassName": "standard",
        "resources": {"requests": {"storage": "10Gi"}},
        "volumeName": "pvc-demo",
        "accessModes": ["ReadWriteOnce"],
        "volumeMode": "Filesystem",
    },
    "status": {
        "phase": "Bound",
        "capacity": {"storage": "128Mi"},
        "accessModes": ["ReadWriteOnce"],
    },
}


class StubPersistentVolumeClaimSetSizeClient:
    """Patch-capable stub for PersistentVolumeClaim set_size.

    Namespaced: path includes namespace segment.
    Captures the most recent ``patch_json`` call for assertion.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """set_size tests do not call GET."""

        raise AssertionError(f"unexpected get on {path!r}")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and return a fake post-patch payload."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        expected_path = (
            "/k8s/clusters/local/api/v1/namespaces/"
            "storage-validation/persistentvolumeclaims/demo-claim"
        )
        if path == expected_path:
            assert params is None
            return _PATCHED_PVC_RESIZED_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_set_size_round_trip() -> None:
    """PATCH path must be namespaced; body is {spec: {resources: {requests: {storage: …}}}}."""

    reset_rate_limit_state()
    client = StubPersistentVolumeClaimSetSizeClient()

    result = await rancher_persistent_volume_claim_set_size(
        namespace="storage-validation",
        claim_name="demo-claim",
        storage="10Gi",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Namespaced path — includes namespace segment.
    assert client.last_patch_path == (
        "/k8s/clusters/local/api/v1/namespaces/storage-validation/persistentvolumeclaims/demo-claim"
    )
    # Body: codegen nests dotted target_path keys (substrate evolution).
    # target_path "spec.resources.requests" -> nested {spec: {resources: {requests: {...}}}}.
    assert client.last_patch_payload == {"spec": {"resources": {"requests": {"storage": "10Gi"}}}}

    # Response is parsed through the get pipeline.
    assert result.name == "demo-claim"
    assert result.ok is True
    assert result.action == "set_size"
    assert result.changed == {"storage": "10Gi"}


@pytest.mark.asyncio
async def test_rancher_persistent_volume_claim_set_size_emits_audit() -> None:
    """Audit record must carry operation=persistent_volume_claim_set_size."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_persistent_volume_claim_set_size(
            namespace="storage-validation",
            claim_name="demo-claim",
            storage="10Gi",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPersistentVolumeClaimSetSizeClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "persistent_volume_claim_set_size"
    assert record["outcome"] == "success"
    assert "storage" in record["arg_keys"]
