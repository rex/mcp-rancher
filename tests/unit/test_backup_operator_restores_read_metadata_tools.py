# ruff: noqa: S105
"""Curated Restore read + metadata tests (list, get, set_labels, set_annotations).

The S105 noqa suppresses bandit's hardcoded-password rule for the test
fixtures' ``encryption-config`` secret-name string literal, which is just
a non-secret K8s resource name.
"""

from __future__ import annotations

import pytest
from _backup_operator_support import (
    _RESTORE_PAYLOAD,
    StubBackupOperatorClient,
    build_settings,
)
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.backup_operator import (
    rancher_restore_get,
    rancher_restore_set_annotations,
    rancher_restore_set_labels,
    rancher_restores_list,
)


@pytest.mark.asyncio
async def test_rancher_restores_list_summarizes_target_filename() -> None:
    """Restore list should expose the source filename and prune flag."""

    result = await rancher_restores_list(
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubBackupOperatorClient(),
    )

    assert result.restore_count == 1
    [restore] = result.restores
    assert restore.name == "demo-restore"
    assert restore.backup_filename == "weekly-backup-2026-01-01.tar.gz"
    assert restore.encryption_config_secret_name == "encryption-config"
    assert restore.prune_value is True
    assert restore.restore_completion_ts == "2026-01-02T00:00:00Z"
    assert restore.summary_state == "ready"


@pytest.mark.asyncio
async def test_rancher_restore_get_renders_default_storage_location() -> None:
    """Detail should report `default` when the operator's default storage is used."""

    result = await rancher_restore_get(
        restore_name="demo-restore",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubBackupOperatorClient(),
    )

    assert result.name == "demo-restore"
    assert result.storage_location_summary == "default"
    assert result.condition_types_true == ["Ready"]
    assert result.payload == _RESTORE_PAYLOAD


# rancher_restore_set_labels (PatchConfig substrate — cluster-scoped, no namespace)
# ==================================================================================


class StubRestoreSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the restore set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path (cluster-scoped — no namespace
    segment), then echoes the restore payload back with updated labels.
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
        """Capture the merge-patch and echo a Kubernetes-shaped restore response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/local/apis/resources.cattle.io/v1/restores/demo-restore"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-restore",
                    "labels": new_labels,
                    "annotations": {},
                },
                "spec": {
                    "backupFilename": "weekly-backup-2026-01-01.tar.gz",
                    "encryptionConfigSecretName": "encryption-config",
                    "prune": True,
                    "storageLocation": {"default": {}},
                },
                "status": {
                    "restoreCompletionTs": "2026-01-02T00:00:00Z",
                    "summary": "ready",
                    "conditions": [
                        {"type": "Ready", "status": "True"},
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_restore_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the cluster-scoped detail path."""

    reset_rate_limit_state()
    client = StubRestoreSetLabelsClient()

    result = await rancher_restore_set_labels(
        restore_name="demo-restore",
        labels={"env": "prod", "team": "ops"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is cluster-scoped — NO namespace segment.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/resources.cattle.io/v1/restores/demo-restore"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "ops"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-restore"


@pytest.mark.asyncio
async def test_rancher_restore_set_labels_emits_audit() -> None:
    """Audit record must carry operation='restore_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_restore_set_labels(
            restore_name="demo-restore",
            labels={"app": "restore"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubRestoreSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_restore_set_labels"
    assert record["operation"] == "restore_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_restore_set_annotations (PatchConfig substrate — cluster-scoped, no namespace)
# =======================================================================================


class StubRestoreSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the restore set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path (cluster-scoped — no namespace
    segment), then echoes the restore payload back with updated annotations.
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
        """Capture the merge-patch and echo a Kubernetes-shaped restore response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/k8s/clusters/local/apis/resources.cattle.io/v1/restores/demo-restore"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-restore",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {
                    "backupFilename": "weekly-backup-2026-01-01.tar.gz",
                    "encryptionConfigSecretName": "encryption-config",
                    "prune": True,
                    "storageLocation": {"default": {}},
                },
                "status": {
                    "restoreCompletionTs": "2026-01-02T00:00:00Z",
                    "summary": "ready",
                    "conditions": [
                        {"type": "Ready", "status": "True"},
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_restore_set_annotations_round_trip() -> None:
    """PATCH body must be {metadata: {annotations: <dict>}} at the cluster-scoped detail path."""

    reset_rate_limit_state()
    client = StubRestoreSetAnnotationsClient()

    result = await rancher_restore_set_annotations(
        restore_name="demo-restore",
        annotations={"env": "prod", "team": "ops"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is cluster-scoped — NO namespace segment.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/resources.cattle.io/v1/restores/demo-restore"
    )
    # Body is exactly the narrow patch — annotations nested under target_path=metadata.
    expected_annotations = {"env": "prod", "team": "ops"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-restore"


@pytest.mark.asyncio
async def test_rancher_restore_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='restore_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_restore_set_annotations(
            restore_name="demo-restore",
            annotations={"app": "restore"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubRestoreSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_restore_set_annotations"
    assert record["operation"] == "restore_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]
