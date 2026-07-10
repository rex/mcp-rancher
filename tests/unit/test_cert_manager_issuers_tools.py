"""Curated cert-manager Issuer tool tests (list/get + set_labels/set_annotations)."""

from __future__ import annotations

import pytest
from _cert_manager_support import (
    _ISSUER_PAYLOAD,
    StubCertManagerClient,
    build_settings,
)
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.cert_manager import (
    rancher_cert_manager_issuer_get,
    rancher_cert_manager_issuer_set_annotations,
    rancher_cert_manager_issuer_set_labels,
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
