# ruff: noqa: S105, S106
"""Curated config-and-secrets tool tests (configmaps, secrets, service_accounts).

The S105/S106 noqa is intentional: this test file deliberately passes
arguments named ``secret_*`` and asserts on string values like ``"Opaque"``
that ruff's bandit-derived rules flag as possible hardcoded passwords.
"""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.config_secrets import (
    rancher_config_map_get,
    rancher_config_maps_list,
    rancher_secret_get,
    rancher_secrets_list,
    rancher_service_account_get,
    rancher_service_accounts_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated config_secrets tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_CONFIG_MAP_PAYLOAD = {
    "metadata": {
        "name": "demo-config",
        "namespace": "demo",
        "annotations": {"app.kubernetes.io/managed-by": "rancher"},
    },
    "data": {
        "config.yaml": "key: value",
        "extra.json": "{}",
    },
    "binaryData": {
        "blob.bin": "AAAA",
    },
    "immutable": False,
}

_SECRET_PAYLOAD = {
    "metadata": {
        "name": "demo-secret",
        "namespace": "demo",
        "annotations": {"app.kubernetes.io/managed-by": "rancher"},
    },
    "type": "Opaque",
    "data": {
        "password": "c2VjcmV0",
        "api-key": "Zm9vYmFy",
    },
    "immutable": True,
}

_SERVICE_ACCOUNT_PAYLOAD = {
    "metadata": {
        "name": "demo-sa",
        "namespace": "demo",
        "annotations": {"description": "demo service account"},
    },
    "secrets": [
        {"name": "demo-sa-token-abc"},
        {"name": "demo-sa-token-def"},
    ],
    "imagePullSecrets": [
        {"name": "regcred"},
    ],
    "automountServiceAccountToken": False,
}


class StubConfigSecretsClient:
    """Deterministic raw Kubernetes proxy client for curated config-secrets tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake raw Kubernetes core-API payloads."""

        cm_root = "/k8s/clusters/local/api/v1/namespaces/demo/configmaps"
        if path == cm_root:
            assert params == {"limit": 5}
            return {"items": [_CONFIG_MAP_PAYLOAD]}
        if path == f"{cm_root}/demo-config":
            assert params is None
            return _CONFIG_MAP_PAYLOAD

        sec_root = "/k8s/clusters/local/api/v1/namespaces/demo/secrets"
        if path == sec_root:
            assert params == {"limit": 5}
            return {"items": [_SECRET_PAYLOAD]}
        if path == f"{sec_root}/demo-secret":
            assert params is None
            return _SECRET_PAYLOAD

        sa_root = "/k8s/clusters/local/api/v1/namespaces/demo/serviceaccounts"
        if path == sa_root:
            assert params == {"limit": 5}
            return {"items": [_SERVICE_ACCOUNT_PAYLOAD]}
        if path == f"{sa_root}/demo-sa":
            assert params is None
            return _SERVICE_ACCOUNT_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")


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


@pytest.mark.asyncio
async def test_rancher_service_accounts_list_counts_secrets_and_pull_secrets() -> None:
    """List should count secrets and image pull secrets."""

    result = await rancher_service_accounts_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    assert result.service_account_count == 1
    [sa] = result.service_accounts
    assert sa.name == "demo-sa"
    assert sa.secret_count == 2
    assert sa.image_pull_secret_count == 1
    assert sa.automount_token is False


@pytest.mark.asyncio
async def test_rancher_service_account_get_returns_named_refs() -> None:
    """Detail should expose secret_names and image_pull_secret_names."""

    result = await rancher_service_account_get(
        namespace="demo",
        service_account_name="demo-sa",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    assert result.name == "demo-sa"
    assert result.secret_names == ["demo-sa-token-abc", "demo-sa-token-def"]
    assert result.image_pull_secret_names == ["regcred"]
    assert result.annotation_keys == ["description"]
    assert result.payload == _SERVICE_ACCOUNT_PAYLOAD
