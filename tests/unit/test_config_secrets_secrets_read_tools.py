# ruff: noqa: S105, S106
"""Curated Secret read + payload-composer tests (list, get, build_secret_payload)."""

from __future__ import annotations

import pytest
from _config_secrets_support import StubConfigSecretsClient, build_settings

from rancher_mcp.tools.config_secrets import (
    rancher_secret_get,
    rancher_secrets_list,
)
from rancher_mcp.tools.config_secrets.shared import build_secret_payload


@pytest.mark.asyncio
async def test_rancher_secrets_list_masks_values_and_exposes_type() -> None:
    """List should expose secret_type and key counts but never values."""

    result = await rancher_secrets_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    assert result.secret_count == 1
    [sec] = result.secrets
    assert sec.name == "demo-secret"
    assert sec.secret_type == "Opaque"
    assert sec.data_key_count == 2
    assert sec.immutable is True
    # Defensively: the typed summary must NOT carry data values.
    assert "data" not in sec.model_dump()


@pytest.mark.asyncio
async def test_rancher_secrets_list_filters_by_type() -> None:
    """secret_type filter should drop entries whose type doesn't match."""

    result = await rancher_secrets_list(
        namespace="demo",
        cluster_id="local",
        secret_type="kubernetes.io/dockerconfigjson",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    assert result.secret_count == 0
    assert result.secrets == []


@pytest.mark.asyncio
async def test_rancher_secret_get_omits_payload_field() -> None:
    """Detail must expose data_keys but never the data values, and lack a payload field."""

    result = await rancher_secret_get(
        namespace="demo",
        secret_name="demo-secret",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    assert result.name == "demo-secret"
    assert result.secret_type == "Opaque"
    assert result.data_key_count == 2
    assert result.data_keys == ["api-key", "password"]
    assert result.annotation_keys == ["app.kubernetes.io/managed-by"]
    # Critical mask check: serialized output must NOT contain a payload field.
    dumped = result.model_dump()
    assert "payload" not in dumped
    # And no raw base64 values.
    assert "c2VjcmV0" not in str(dumped)
    assert "Zm9vYmFy" not in str(dumped)


# =====================================================================
# build_secret_payload composer tests
# =====================================================================


def test_build_secret_payload_with_string_data_only() -> None:
    """Plaintext string_data goes into stringData; data field omitted."""

    payload = build_secret_payload(
        name="demo-secret",
        namespace="demo",
        string_data={"password": "hunter2"},
    )

    assert payload == {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "demo-secret", "namespace": "demo"},
        "stringData": {"password": "hunter2"},
    }
    # data field is NOT in the payload when only string_data is given.
    assert "data" not in payload


def test_build_secret_payload_with_data_only_and_secret_type() -> None:
    """Already-base64 data goes into `data`; stringData omitted."""

    payload = build_secret_payload(
        name="demo-secret",
        namespace="demo",
        data={"password": "aHVudGVyMg=="},
        secret_type="kubernetes.io/dockerconfigjson",
        immutable=True,
    )

    assert payload == {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "demo-secret", "namespace": "demo"},
        "data": {"password": "aHVudGVyMg=="},
        "type": "kubernetes.io/dockerconfigjson",
        "immutable": True,
    }
    assert "stringData" not in payload


def test_build_secret_payload_refuses_when_both_data_sources_empty() -> None:
    """Composer rejects empty payloads — secrets must store at least one entry."""

    with pytest.raises(ValueError, match="non-empty"):
        build_secret_payload(name="x", namespace="demo")
