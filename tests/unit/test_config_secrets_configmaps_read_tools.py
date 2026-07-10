"""Curated ConfigMap read + payload-composer tests (list, get, build_configmap_payload)."""

from __future__ import annotations

import pytest
from _config_secrets_support import _CONFIG_MAP_PAYLOAD, StubConfigSecretsClient, build_settings

from rancher_mcp.tools.config_secrets import (
    rancher_config_map_get,
    rancher_config_maps_list,
)
from rancher_mcp.tools.config_secrets.shared import build_configmap_payload


@pytest.mark.asyncio
async def test_rancher_config_maps_list_counts_data_and_binary_data() -> None:
    """List should count data and binary data keys without exposing values."""

    result = await rancher_config_maps_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    assert result.config_map_count == 1
    [cm] = result.config_maps
    assert cm.name == "demo-config"
    assert cm.data_key_count == 2
    assert cm.binary_data_key_count == 1
    assert cm.immutable is False


@pytest.mark.asyncio
async def test_rancher_config_map_get_includes_keys_and_payload() -> None:
    """Detail should include data_keys, binary_data_keys, annotations, and full payload."""

    result = await rancher_config_map_get(
        namespace="demo",
        config_map_name="demo-config",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    assert result.name == "demo-config"
    assert result.data_keys == ["config.yaml", "extra.json"]
    assert result.binary_data_keys == ["blob.bin"]
    assert result.annotation_keys == ["app.kubernetes.io/managed-by"]
    assert result.payload == _CONFIG_MAP_PAYLOAD


# =====================================================================
# build_configmap_payload composer (pure-function unit tests)
# =====================================================================


def test_build_configmap_payload_minimal_required_fields() -> None:
    """Composer with only required args produces a Kubernetes-shaped POST body."""

    payload = build_configmap_payload(
        name="demo-config",
        namespace="demo",
        data={"key": "value"},
    )

    assert payload == {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "demo-config", "namespace": "demo"},
        "data": {"key": "value"},
    }


def test_build_configmap_payload_omits_none_optional_fields() -> None:
    """Composer must NOT emit binaryData/immutable/labels/annotations when None.

    Sending those keys with empty/null values changes Kubernetes
    apply-merge semantics — the composer's contract is that None
    means "don't touch this field on the server".
    """

    payload = build_configmap_payload(
        name="demo-config",
        namespace="demo",
        data={"key": "value"},
        binary_data=None,
        immutable=None,
        labels=None,
        annotations=None,
    )

    assert payload == {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "demo-config", "namespace": "demo"},
        "data": {"key": "value"},
    }
    assert "binaryData" not in payload
    assert "immutable" not in payload


def test_build_configmap_payload_includes_optional_fields_when_set() -> None:
    """Composer wires optional args into the right payload slots when set."""

    payload = build_configmap_payload(
        name="demo-config",
        namespace="demo",
        data={"k": "v"},
        binary_data={"b": "AAAA"},
        immutable=True,
        labels={"app": "demo"},
        annotations={"owner": "ops"},
    )

    assert payload == {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": "demo-config",
            "namespace": "demo",
            "labels": {"app": "demo"},
            "annotations": {"owner": "ops"},
        },
        "data": {"k": "v"},
        "binaryData": {"b": "AAAA"},
        "immutable": True,
    }
