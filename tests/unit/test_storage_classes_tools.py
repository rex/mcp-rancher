"""Curated StorageClass tool tests (list/get/default-only + delete)."""

from __future__ import annotations

import pytest
from _storage_support import StubRawK8sClient, build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.storage import (
    rancher_storage_class_delete,
    rancher_storage_class_get,
    rancher_storage_classes_list,
)


@pytest.mark.asyncio
async def test_rancher_storage_classes_list_returns_typed_summaries() -> None:
    """Curated storage-class list should expose typed storage-class summaries."""

    result = await rancher_storage_classes_list(
        cluster_id="venue-local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.instance == "work"
    assert result.cluster_id == "venue-local"
    assert result.storage_class_count == 1
    assert result.applied_query_params == {"limit": 5}
    assert result.storage_classes[0].name == "standard"
    assert result.storage_classes[0].default_class is True


@pytest.mark.asyncio
async def test_rancher_storage_class_get_returns_typed_detail() -> None:
    """Curated storage-class detail should expose annotation and mount-option detail."""

    result = await rancher_storage_class_get(
        storage_class_name="standard",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubRawK8sClient(),
    )

    assert result.name == "standard"
    assert result.provisioner == "rancher.io/local-path"
    assert result.mount_options == ["discard"]


@pytest.mark.asyncio
async def test_rancher_storage_classes_list_applies_default_only_filter() -> None:
    """Curated storage-class list should filter to default classes when requested."""

    class MixedStorageClassClient:
        """Deterministic storage-class client with default and non-default entries."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return mixed storage-class payloads."""

            assert path == "/k8s/clusters/venue-local/apis/storage.k8s.io/v1/storageclasses"
            assert params is None
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "standard",
                            "annotations": {
                                "storageclass.kubernetes.io/is-default-class": "true",
                            },
                        },
                        "provisioner": "rancher.io/local-path",
                    },
                    {
                        "metadata": {
                            "name": "slow",
                            "annotations": {
                                "storageclass.kubernetes.io/is-default-class": "false",
                            },
                        },
                        "provisioner": "kubernetes.io/noop",
                    },
                ]
            }

    result = await rancher_storage_classes_list(
        cluster_id="venue-local",
        default_only=True,
        instance="work",
        settings=build_settings(),
        client=MixedStorageClassClient(),
    )

    assert result.storage_class_count == 1
    assert [storage_class.name for storage_class in result.storage_classes] == ["standard"]


# =====================================================================
# StorageClass delete
# =====================================================================


class StubStorageClassDeleteClient:
    """Delete-capable stub for StorageClass delete.

    Cluster-scoped: no namespace segment in the path.
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

        del payload  # unused for k8s storage class deletes
        self.last_delete_path = path
        return {"apiVersion": "v1", "kind": "Status", "status": "Success"}


@pytest.mark.asyncio
async def test_rancher_storage_class_delete_refuses_wrong_confirmation() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubStorageClassDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_storage_class_delete(
            storage_class_name="standard",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete storage_class standard" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_storage_class_delete_routes_to_delete_json() -> None:
    """Correct confirmation phrase routes to delete_json on the cluster-scoped detail path."""

    reset_rate_limit_state()
    client = StubStorageClassDeleteClient()

    result = await rancher_storage_class_delete(
        storage_class_name="standard",
        confirmation="delete storage_class standard",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/storage.k8s.io/v1/storageclasses/standard"
    )
    assert result.deleted is True
    assert result.resource_kind == "storage_class"
    assert result.resource_name == "standard"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete storage_class standard"
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_storage_classes_list"]


@pytest.mark.asyncio
async def test_rancher_storage_class_delete_emits_audit() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    _good_phrase = "delete storage_class standard"
    with capture_logs() as success_logs:
        await rancher_storage_class_delete(
            storage_class_name="standard",
            confirmation=_good_phrase,
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubStorageClassDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "storage_class_delete"
    assert success_audits[0]["outcome"] == "success"

    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_storage_class_delete(
            storage_class_name="standard",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubStorageClassDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "storage_class_delete"
    assert reject_audits[0]["outcome"] == "error"
