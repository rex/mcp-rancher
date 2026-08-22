"""Curated StorageClass tool tests (list/get/default-only)."""

from __future__ import annotations

import pytest
from _storage_support import StubRawK8sClient, build_settings

from rancher_mcp.tools.storage import (
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
