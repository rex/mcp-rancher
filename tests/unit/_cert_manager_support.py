# ruff: noqa: S105
"""Shared setup for the curated cert-manager tool test suites.

Extracted from ``test_cert_manager_tools.py`` when it was split by
resource/operation to stay under the architecture line limit.
``build_settings``, the shared payload constants, and the shared read
stub ``StubCertManagerClient`` are consumed by the cert-manager
list/get test modules; operation-specific stubs stay with the tests
that use them.

The S105 noqa suppresses bandit's hardcoded-password rule for the
test fixture's ``demo-tls-secret`` string literal — that's a Kubernetes
secret resource name, not a password.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


def build_settings() -> AppSettings:
    """Create deterministic settings for cert-manager tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_CERTIFICATE_PAYLOAD = {
    "metadata": {
        "name": "demo-tls",
        "namespace": "demo",
        "annotations": {"cert-manager.io/issue-temporary-certificate": "true"},
    },
    "spec": {
        "commonName": "demo.example.com",
        "dnsNames": ["demo.example.com", "www.demo.example.com"],
        "secretName": "demo-tls-secret",
        "issuerRef": {"kind": "ClusterIssuer", "name": "letsencrypt-prod"},
    },
    "status": {
        "notAfter": "2026-12-01T00:00:00Z",
        "notBefore": "2026-09-01T00:00:00Z",
        "renewalTime": "2026-11-01T00:00:00Z",
        "conditions": [
            {"type": "Ready", "status": "True"},
            {"type": "Issuing", "status": "False"},
        ],
    },
}

_ISSUER_PAYLOAD = {
    "metadata": {
        "name": "demo-issuer",
        "namespace": "demo",
        "annotations": {},
    },
    "spec": {
        "acme": {
            "server": "https://acme-v02.api.letsencrypt.org/directory",
            "email": "ops@example.com",
        },
    },
    "status": {
        "conditions": [
            {"type": "Ready", "status": "True"},
        ],
    },
}

_CLUSTER_ISSUER_PAYLOAD = {
    "metadata": {
        "name": "letsencrypt-prod",
        "annotations": {},
    },
    "spec": {
        "acme": {
            "server": "https://acme-v02.api.letsencrypt.org/directory",
            "email": "platform@example.com",
        },
    },
    "status": {
        "conditions": [
            {"type": "Ready", "status": "True"},
        ],
    },
}


class StubCertManagerClient:
    """Deterministic raw Kubernetes proxy client for cert-manager tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake cert-manager.io/v1 CRD payloads."""

        ns_root = "/k8s/clusters/local/apis/cert-manager.io/v1/namespaces/demo"
        cluster_root = "/k8s/clusters/local/apis/cert-manager.io/v1"

        if path == f"{ns_root}/certificates":
            assert params == {"limit": 5}
            return {"items": [_CERTIFICATE_PAYLOAD]}
        if path == f"{ns_root}/certificates/demo-tls":
            assert params is None
            return _CERTIFICATE_PAYLOAD

        if path == f"{ns_root}/issuers":
            assert params == {"limit": 5}
            return {"items": [_ISSUER_PAYLOAD]}
        if path == f"{ns_root}/issuers/demo-issuer":
            assert params is None
            return _ISSUER_PAYLOAD

        if path == f"{cluster_root}/clusterissuers":
            assert params == {"limit": 5}
            return {"items": [_CLUSTER_ISSUER_PAYLOAD]}
        if path == f"{cluster_root}/clusterissuers/letsencrypt-prod":
            assert params is None
            return _CLUSTER_ISSUER_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")
