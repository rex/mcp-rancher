"""Curated certificate-inventory tool tests.

Covers `certificates` (project-scoped) and `namespaced_certificates`
(namespace-scoped). Both detail tools omit the raw payload by design
(the Norman certificate type carries the private-key PEM in `key`).
"""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.certificates import (
    rancher_certificate_get,
    rancher_certificates_list,
    rancher_namespaced_certificate_get,
    rancher_namespaced_certificates_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated certificate tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_CERTIFICATE_PAYLOAD = {
    "id": "c-local:p-demo:cert-tls-1",
    "type": "certificate",
    "name": "demo-tls",
    "state": "active",
    "cn": "demo.example.com",
    "issuer": "Let's Encrypt Authority X3",
    "expiresAt": "2026-12-01T00:00:00Z",
    "issuedAt": "2025-12-01T00:00:00Z",
    "serialNumber": "abc123def456",
    "algorithm": "RSA",
    "keySize": 2048,
    "version": "3",
    "subjectAlternativeNames": ["demo.example.com", "www.demo.example.com"],
    "fingerprintSha1": "AA:BB:CC",
    "fingerprintSha256": "11:22:33:44:55",
    "cnList": ["demo.example.com"],
    "projectId": "c-local:p-demo",
    "certs": "-----BEGIN CERTIFICATE-----\nFAKEPEM\n-----END CERTIFICATE-----",
    "key": "-----BEGIN PRIVATE KEY-----\nFAKEPRIVATEKEY\n-----END PRIVATE KEY-----",
    "actions": {},
    "links": {"self": "..."},
}

_NAMESPACED_CERTIFICATE_PAYLOAD = {
    "id": "c-local:p-demo:ns-cert-1",
    "type": "namespacedCertificate",
    "name": "demo-ns-tls",
    "state": "active",
    "cn": "ns.example.com",
    "issuer": "Internal CA",
    "expiresAt": "2027-01-15T00:00:00Z",
    "serialNumber": "ns-cert-serial",
    "algorithm": "ECDSA",
    "keySize": 256,
    "namespaceId": "demo-ns",
    "projectId": "c-local:p-demo",
    "subjectAlternativeNames": ["ns.example.com"],
    "fingerprintSha1": "DD:EE:FF",
    "fingerprintSha256": "AA:BB:CC:DD:EE",
    "cnList": ["ns.example.com"],
    "version": "3",
    "certs": "-----BEGIN CERTIFICATE-----\nFAKEPEM2\n-----END CERTIFICATE-----",
    "key": "-----BEGIN EC PRIVATE KEY-----\nFAKEECKEY\n-----END EC PRIVATE KEY-----",
    "actions": {},
    "links": {"self": "..."},
}


class StubCertificatesClient:
    """Deterministic Rancher Norman client for curated certificate tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake Rancher Norman certificate payloads."""

        if path == "/v3/certificates":
            assert params == {"limit": 5}
            return {"data": [_CERTIFICATE_PAYLOAD]}
        if path == "/v3/certificates/c-local:p-demo:cert-tls-1":
            assert params is None
            return _CERTIFICATE_PAYLOAD

        if path == "/v3/namespacedcertificates":
            assert params == {"limit": 5}
            return {"data": [_NAMESPACED_CERTIFICATE_PAYLOAD]}
        if path == "/v3/namespacedcertificates/c-local:p-demo:ns-cert-1":
            assert params is None
            return _NAMESPACED_CERTIFICATE_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")


@pytest.mark.asyncio
async def test_rancher_certificates_list_summarizes_metadata() -> None:
    """List should expose cn, issuer, expiresAt, algorithm, key_size."""

    result = await rancher_certificates_list(
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubCertificatesClient(),
    )

    assert result.certificate_count == 1
    [cert] = result.certificates
    assert cert.id == "c-local:p-demo:cert-tls-1"
    assert cert.cn == "demo.example.com"
    assert cert.issuer == "Let's Encrypt Authority X3"
    assert cert.expires_at == "2026-12-01T00:00:00Z"
    assert cert.algorithm == "RSA"
    assert cert.key_size == 2048
    # Defensive: summary serialization must NOT include cert/key PEM.
    dumped = cert.model_dump()
    assert "certs" not in dumped
    assert "key" not in dumped
    assert "FAKEPRIVATEKEY" not in str(dumped)


@pytest.mark.asyncio
async def test_rancher_certificate_get_omits_payload_field() -> None:
    """Detail must NOT include payload field (which would expose key PEM)."""

    result = await rancher_certificate_get(
        certificate_id="c-local:p-demo:cert-tls-1",
        instance="work",
        settings=build_settings(),
        client=StubCertificatesClient(),
    )

    assert result.id == "c-local:p-demo:cert-tls-1"
    assert result.cn == "demo.example.com"
    assert result.subject_alternative_names == [
        "demo.example.com",
        "www.demo.example.com",
    ]
    assert result.fingerprint_sha1 == "AA:BB:CC"
    assert result.fingerprint_sha256 == "11:22:33:44:55"
    # Critical mask checks.
    dumped = result.model_dump()
    assert "payload" not in dumped
    assert "certs" not in dumped
    assert "key" not in dumped
    assert "FAKEPRIVATEKEY" not in str(dumped)


@pytest.mark.asyncio
async def test_rancher_namespaced_certificates_list_returns_summary() -> None:
    """Namespaced list should expose namespace_id and project_id."""

    result = await rancher_namespaced_certificates_list(
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubCertificatesClient(),
    )

    assert result.namespaced_certificate_count == 1
    [cert] = result.namespaced_certificates
    assert cert.id == "c-local:p-demo:ns-cert-1"
    assert cert.namespace_id == "demo-ns"
    assert cert.project_id == "c-local:p-demo"
    assert cert.algorithm == "ECDSA"


@pytest.mark.asyncio
async def test_rancher_namespaced_certificate_get_omits_payload() -> None:
    """Namespaced detail must mask PEM bytes the same way."""

    result = await rancher_namespaced_certificate_get(
        certificate_id="c-local:p-demo:ns-cert-1",
        instance="work",
        settings=build_settings(),
        client=StubCertificatesClient(),
    )

    assert result.id == "c-local:p-demo:ns-cert-1"
    assert result.cn == "ns.example.com"
    assert result.namespace_id == "demo-ns"
    assert result.fingerprint_sha256 == "AA:BB:CC:DD:EE"
    dumped = result.model_dump()
    assert "payload" not in dumped
    assert "certs" not in dumped
    assert "key" not in dumped
    assert "FAKEECKEY" not in str(dumped)
