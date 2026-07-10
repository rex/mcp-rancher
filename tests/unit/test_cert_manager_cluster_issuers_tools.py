"""Curated cert-manager ClusterIssuer tool tests (list/get + set_labels/set_annotations)."""

from __future__ import annotations

import pytest
from _cert_manager_support import (
    _CLUSTER_ISSUER_PAYLOAD,
    StubCertManagerClient,
    build_settings,
)
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.cert_manager import (
    rancher_cert_manager_cluster_issuer_get,
    rancher_cert_manager_cluster_issuer_set_annotations,
    rancher_cert_manager_cluster_issuer_set_labels,
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


# rancher_cert_manager_cluster_issuer_set_annotations (multi-patch substrate — cluster-scoped)
# =============================================================================================


class StubCertManagerClusterIssuerSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the cluster_issuer set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the cluster
    issuer payload back with the supplied annotations applied.  No namespace
    segment in the path — ClusterIssuer is cluster-scoped.
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
        """Capture the merge-patch and echo a Kubernetes-shaped cluster issuer response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/local/apis/cert-manager.io/v1/clusterissuers/letsencrypt-prod"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "letsencrypt-prod",
                    "labels": {},
                    "annotations": new_annotations,
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
async def test_rancher_cert_manager_cluster_issuer_set_annotations_round_trip() -> None:
    """PATCH body must be {metadata: {annotations: <dict>}} at the cluster-scoped detail path."""

    reset_rate_limit_state()
    client = StubCertManagerClusterIssuerSetAnnotationsClient()

    result = await rancher_cert_manager_cluster_issuer_set_annotations(
        cluster_issuer_name="letsencrypt-prod",
        annotations={"cert-manager.io/issue-temporary-certificate": "true"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path has NO namespace segment — ClusterIssuer is cluster-scoped.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/cert-manager.io/v1/clusterissuers/letsencrypt-prod"
    )
    # Body is exactly the narrow patch — annotations nested under target_path=metadata.
    expected_annotations = {"cert-manager.io/issue-temporary-certificate": "true"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "letsencrypt-prod"


@pytest.mark.asyncio
async def test_rancher_cert_manager_cluster_issuer_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='cert_manager_cluster_issuer_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_cert_manager_cluster_issuer_set_annotations(
            cluster_issuer_name="letsencrypt-prod",
            annotations={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubCertManagerClusterIssuerSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_cert_manager_cluster_issuer_set_annotations"
    assert record["operation"] == "cert_manager_cluster_issuer_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
