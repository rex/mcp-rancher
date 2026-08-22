"""Curated ServiceAccount read tests (list, get)."""

from __future__ import annotations

import pytest
from _config_secrets_support import (
    _SERVICE_ACCOUNT_PAYLOAD,
    StubConfigSecretsClient,
    build_settings,
)

from rancher_mcp.tools.config_secrets import (
    rancher_service_account_get,
    rancher_service_accounts_list,
)


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
