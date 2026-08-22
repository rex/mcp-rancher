"""Curated cert-manager ClusterIssuer tool tests (list/get)."""

from __future__ import annotations

import pytest
from _cert_manager_support import (
    _CLUSTER_ISSUER_PAYLOAD,
    StubCertManagerClient,
    build_settings,
)

from rancher_mcp.tools.cert_manager import (
    rancher_cert_manager_cluster_issuer_get,
    rancher_cert_manager_cluster_issuers_list,
)


@pytest.mark.asyncio
async def test_rancher_cert_manager_cluster_issuers_list_returns_summary() -> None:
    """ClusterIssuer list should work cluster-scoped (no namespace path)."""

    result = await rancher_cert_manager_cluster_issuers_list(
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubCertManagerClient(),
    )

    assert result.cert_manager_cluster_issuer_count == 1
    [ci] = result.cert_manager_cluster_issuers
    assert ci.name == "letsencrypt-prod"
    assert ci.issuer_kind_used == "acme"
    assert ci.acme_email == "platform@example.com"
    assert ci.ready is True


@pytest.mark.asyncio
async def test_rancher_cert_manager_cluster_issuer_get_returns_detail() -> None:
    """ClusterIssuer detail should expose condition types."""

    result = await rancher_cert_manager_cluster_issuer_get(
        cluster_issuer_name="letsencrypt-prod",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubCertManagerClient(),
    )

    assert result.name == "letsencrypt-prod"
    assert result.condition_types_true == ["Ready"]
    assert result.payload == _CLUSTER_ISSUER_PAYLOAD
