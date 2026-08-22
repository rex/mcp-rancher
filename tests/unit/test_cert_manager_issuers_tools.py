"""Curated cert-manager Issuer tool tests (list/get)."""

from __future__ import annotations

import pytest
from _cert_manager_support import (
    _ISSUER_PAYLOAD,
    StubCertManagerClient,
    build_settings,
)

from rancher_mcp.tools.cert_manager import (
    rancher_cert_manager_issuer_get,
    rancher_cert_manager_issuers_list,
)


@pytest.mark.asyncio
async def test_rancher_cert_manager_issuers_list_detects_kind() -> None:
    """List should detect issuer_kind_used (acme/ca/vault/selfSigned/venafi)."""

    result = await rancher_cert_manager_issuers_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubCertManagerClient(),
    )

    assert result.cert_manager_issuer_count == 1
    [issuer] = result.cert_manager_issuers
    assert issuer.name == "demo-issuer"
    assert issuer.issuer_kind_used == "acme"
    assert issuer.acme_server == "https://acme-v02.api.letsencrypt.org/directory"
    assert issuer.acme_email == "ops@example.com"
    assert issuer.ready is True


@pytest.mark.asyncio
async def test_rancher_cert_manager_issuer_get_returns_detail() -> None:
    """Issuer detail should expose annotation keys + condition types."""

    result = await rancher_cert_manager_issuer_get(
        namespace="demo",
        issuer_name="demo-issuer",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubCertManagerClient(),
    )

    assert result.name == "demo-issuer"
    assert result.condition_types_true == ["Ready"]
    assert result.payload == _ISSUER_PAYLOAD
