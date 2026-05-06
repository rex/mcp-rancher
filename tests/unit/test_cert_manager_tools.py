# ruff: noqa: S105
"""Curated cert-manager tool tests (Certificate, Issuer, ClusterIssuer).

The S105 noqa suppresses bandit's hardcoded-password rule for the
test fixture's ``demo-tls-secret`` string literal — that's a Kubernetes
secret resource name, not a password.
"""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.cert_manager import (
    rancher_cert_manager_certificate_get,
    rancher_cert_manager_certificate_set_annotations,
    rancher_cert_manager_certificate_set_labels,
    rancher_cert_manager_certificates_list,
    rancher_cert_manager_cluster_issuer_get,
    rancher_cert_manager_cluster_issuer_set_labels,
    rancher_cert_manager_cluster_issuers_list,
    rancher_cert_manager_issuer_get,
    rancher_cert_manager_issuer_set_annotations,
    rancher_cert_manager_issuer_set_labels,
    rancher_cert_manager_issuers_list,
)


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


# rancher_cert_manager_certificate_set_labels (PatchConfig substrate — metadata target)
# ======================================================================================


class StubCertManagerCertificateSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the certificate set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the certificate
    payload back with the supplied labels applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_labels tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Kubernetes-shaped certificate response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/cert-manager.io/v1/namespaces/demo/certificates/demo-tls"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-tls",
                    "namespace": "demo",
                    "labels": new_labels,
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

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cert_manager_certificate_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubCertManagerCertificateSetLabelsClient()

    result = await rancher_cert_manager_certificate_set_labels(
        namespace="demo",
        certificate_name="demo-tls",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/cert-manager.io/v1/namespaces/demo/certificates/demo-tls"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-tls"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_cert_manager_certificate_set_labels_emits_audit() -> None:
    """Audit record must carry operation='cert_manager_certificate_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cert_manager_certificate_set_labels(
            namespace="demo",
            certificate_name="demo-tls",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCertManagerCertificateSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cert_manager_certificate_set_labels"
    assert record["operation"] == "cert_manager_certificate_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_cert_manager_certificate_set_annotations (multi-patch substrate — metadata target)
# ==========================================================================================


class StubCertManagerCertificateSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the certificate set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the certificate
    payload back with the supplied annotations applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_annotations tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Kubernetes-shaped certificate response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/cert-manager.io/v1/namespaces/demo/certificates/demo-tls"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-tls",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": new_annotations,
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

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cert_manager_certificate_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubCertManagerCertificateSetAnnotationsClient()

    result = await rancher_cert_manager_certificate_set_annotations(
        namespace="demo",
        certificate_name="demo-tls",
        annotations={"cert-manager.io/issue-temporary-certificate": "true"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/cert-manager.io/v1/namespaces/demo/certificates/demo-tls"
    )
    # Body is exactly the narrow patch — annotations nested under target_path=metadata.
    expected_annotations = {"cert-manager.io/issue-temporary-certificate": "true"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-tls"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_cert_manager_certificate_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='cert_manager_certificate_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cert_manager_certificate_set_annotations(
            namespace="demo",
            certificate_name="demo-tls",
            annotations={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCertManagerCertificateSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cert_manager_certificate_set_annotations"
    assert record["operation"] == "cert_manager_certificate_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


# rancher_cert_manager_issuer_set_labels (single-patch substrate — metadata target)
# ==================================================================================


class StubCertManagerIssuerSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the issuer set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the issuer
    payload back with the supplied labels applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_labels tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Kubernetes-shaped issuer response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/cert-manager.io/v1/namespaces/demo/issuers/demo-issuer"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-issuer",
                    "namespace": "demo",
                    "labels": new_labels,
                    "annotations": {},
                },
                "spec": {
                    "acme": {
                        "server": "https://acme-v02.api.letsencrypt.org/directory",
                        "email": "ops@example.com",
                        "privateKeySecretRef": {"name": "letsencrypt-key"},
                        "solvers": [],
                    }
                },
                "status": {
                    "conditions": [{"type": "Ready", "status": "True"}],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cert_manager_issuer_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubCertManagerIssuerSetLabelsClient()

    result = await rancher_cert_manager_issuer_set_labels(
        namespace="demo",
        issuer_name="demo-issuer",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/cert-manager.io/v1/namespaces/demo/issuers/demo-issuer"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-issuer"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_cert_manager_issuer_set_labels_emits_audit() -> None:
    """Audit record must carry operation='cert_manager_issuer_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cert_manager_issuer_set_labels(
            namespace="demo",
            issuer_name="demo-issuer",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCertManagerIssuerSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cert_manager_issuer_set_labels"
    assert record["operation"] == "cert_manager_issuer_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_cert_manager_issuer_set_annotations (multi-patch substrate — metadata target)
# ======================================================================================


class StubCertManagerIssuerSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the issuer set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the issuer
    payload back with the supplied annotations applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_annotations tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Kubernetes-shaped issuer response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/cert-manager.io/v1/namespaces/demo/issuers/demo-issuer"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-issuer",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {
                    "acme": {
                        "server": "https://acme-v02.api.letsencrypt.org/directory",
                        "email": "ops@example.com",
                        "privateKeySecretRef": {"name": "letsencrypt-key"},
                        "solvers": [],
                    }
                },
                "status": {
                    "conditions": [{"type": "Ready", "status": "True"}],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cert_manager_issuer_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubCertManagerIssuerSetAnnotationsClient()

    result = await rancher_cert_manager_issuer_set_annotations(
        namespace="demo",
        issuer_name="demo-issuer",
        annotations={"cert-manager.io/issuer-kind": "Issuer"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/cert-manager.io/v1/namespaces/demo/issuers/demo-issuer"
    )
    # Body is exactly the narrow patch — annotations nested under target_path=metadata.
    expected_annotations = {"cert-manager.io/issuer-kind": "Issuer"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-issuer"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_cert_manager_issuer_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='cert_manager_issuer_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cert_manager_issuer_set_annotations(
            namespace="demo",
            issuer_name="demo-issuer",
            annotations={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCertManagerIssuerSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cert_manager_issuer_set_annotations"
    assert record["operation"] == "cert_manager_issuer_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


# rancher_cert_manager_cluster_issuer_set_labels (single-patch substrate — cluster-scoped)
# =========================================================================================


class StubCertManagerClusterIssuerSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the cluster_issuer set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the cluster
    issuer payload back with the supplied labels applied.  No namespace
    segment in the path — ClusterIssuer is cluster-scoped.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_labels tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Kubernetes-shaped cluster issuer response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/local/apis/cert-manager.io/v1/clusterissuers/letsencrypt-prod"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "letsencrypt-prod",
                    "labels": new_labels,
                    "annotations": {},
                },
                "spec": {
                    "acme": {
                        "server": "https://acme-v02.api.letsencrypt.org/directory",
                        "email": "platform@example.com",
                        "privateKeySecretRef": {"name": "letsencrypt-key"},
                        "solvers": [],
                    }
                },
                "status": {
                    "conditions": [{"type": "Ready", "status": "True"}],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_cert_manager_cluster_issuer_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the cluster-scoped detail path."""

    reset_rate_limit_state()
    client = StubCertManagerClusterIssuerSetLabelsClient()

    result = await rancher_cert_manager_cluster_issuer_set_labels(
        cluster_issuer_name="letsencrypt-prod",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path has NO namespace segment — ClusterIssuer is cluster-scoped.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/cert-manager.io/v1/clusterissuers/letsencrypt-prod"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "letsencrypt-prod"


@pytest.mark.asyncio
async def test_rancher_cert_manager_cluster_issuer_set_labels_emits_audit() -> None:
    """Audit record must carry operation='cert_manager_cluster_issuer_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cert_manager_cluster_issuer_set_labels(
            cluster_issuer_name="letsencrypt-prod",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCertManagerClusterIssuerSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cert_manager_cluster_issuer_set_labels"
    assert record["operation"] == "cert_manager_cluster_issuer_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]
