# ruff: noqa: S105
"""Curated cert-manager Certificate tool tests (list/get).

The S105 noqa suppresses bandit's hardcoded-password rule for the
test fixture's ``demo-tls-secret`` string literal — that's a Kubernetes
secret resource name, not a password.
"""

from __future__ import annotations

import pytest
from _cert_manager_support import (
    _CERTIFICATE_PAYLOAD,
    StubCertManagerClient,
    build_settings,
)

from rancher_mcp.tools.cert_manager import (
    rancher_cert_manager_certificate_get,
    rancher_cert_manager_certificates_list,
)


@pytest.mark.asyncio
async def test_rancher_cert_manager_certificates_list_returns_summary() -> None:
    """List should expose commonName, dnsNames, secretName, issuerRef, validity dates."""

    result = await rancher_cert_manager_certificates_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubCertManagerClient(),
    )

    assert result.cert_manager_certificate_count == 1
    [cert] = result.cert_manager_certificates
    assert cert.name == "demo-tls"
    assert cert.common_name == "demo.example.com"
    assert cert.dns_names == ["demo.example.com", "www.demo.example.com"]
    assert cert.secret_name == "demo-tls-secret"
    assert cert.issuer_kind == "ClusterIssuer"
    assert cert.issuer_name == "letsencrypt-prod"
    assert cert.not_after == "2026-12-01T00:00:00Z"
    assert cert.renewal_time == "2026-11-01T00:00:00Z"
    assert cert.ready is True


@pytest.mark.asyncio
async def test_rancher_cert_manager_certificate_get_returns_condition_types() -> None:
    """Detail should expose condition_types_true list."""

    result = await rancher_cert_manager_certificate_get(
        namespace="demo",
        certificate_name="demo-tls",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubCertManagerClient(),
    )

    assert result.name == "demo-tls"
    assert result.condition_types_true == ["Ready"]
    assert result.payload == _CERTIFICATE_PAYLOAD
