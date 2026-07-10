"""Curated ServiceAccount read + metadata tests (list, get, set_labels, set_annotations)."""

from __future__ import annotations

import pytest
from _config_secrets_support import (
    _SERVICE_ACCOUNT_PAYLOAD,
    StubConfigSecretsClient,
    build_settings,
)
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.config_secrets import (
    rancher_service_account_get,
    rancher_service_account_set_annotations,
    rancher_service_account_set_labels,
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


# =====================================================================
# rancher_service_account_set_labels (PatchConfig substrate — metadata target)
# =====================================================================


class StubServiceAccountSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the service_account set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the ServiceAccount
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
        """Capture the merge-patch and echo a Kubernetes-shaped ServiceAccount response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/local/api/v1/namespaces/demo/serviceaccounts/demo-sa"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-sa",
                    "namespace": "demo",
                    "labels": new_labels,
                    "annotations": {"description": "demo service account"},
                },
                "secrets": [{"name": "demo-sa-token-abc"}],
                "imagePullSecrets": [],
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_service_account_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubServiceAccountSetLabelsClient()

    result = await rancher_service_account_set_labels(
        namespace="demo",
        service_account_name="demo-sa",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/api/v1/namespaces/demo/serviceaccounts/demo-sa"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-sa"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_service_account_set_labels_emits_audit() -> None:
    """Audit record must carry operation='service_account_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_service_account_set_labels(
            namespace="demo",
            service_account_name="demo-sa",
            labels={"app": "backend"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceAccountSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_service_account_set_labels"
    assert record["operation"] == "service_account_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# =====================================================================
# rancher_service_account_set_annotations (PatchConfig substrate — metadata target)
# =====================================================================


class StubServiceAccountSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the service_account set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the ServiceAccount
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
        """Capture the merge-patch and echo a Kubernetes-shaped ServiceAccount response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/local/api/v1/namespaces/demo/serviceaccounts/demo-sa"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-sa",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "secrets": [{"name": "demo-sa-token-abc"}],
                "imagePullSecrets": [],
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_service_account_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubServiceAccountSetAnnotationsClient()

    result = await rancher_service_account_set_annotations(
        namespace="demo",
        service_account_name="demo-sa",
        annotations={"app.kubernetes.io/managed-by": "helm", "env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_path == (
        "/k8s/clusters/local/api/v1/namespaces/demo/serviceaccounts/demo-sa"
    )
    expected_annotations = {"app.kubernetes.io/managed-by": "helm", "env": "prod"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    assert result.name == "demo-sa"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_service_account_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='service_account_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_service_account_set_annotations(
            namespace="demo",
            service_account_name="demo-sa",
            annotations={"team": "platform"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceAccountSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_service_account_set_annotations"
    assert record["operation"] == "service_account_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
