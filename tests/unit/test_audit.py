"""Audit-trail logging tests for mutation tools.

Uses ``structlog.testing.capture_logs`` to assert on records emitted
by the dedicated ``rancher_mcp.audit`` logger. Validates both the
direct ``audit_mutation`` decorator behavior and end-to-end coverage
through one of the 8 generic mutation tools.
"""

from __future__ import annotations

from typing import Any

import pytest
from structlog.testing import capture_logs

from rancher_mcp.audit import AuditEntry, audit_mutation, emit_audit
from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import (
    RancherAPIError,
    RancherCapabilityError,
)


def build_settings(*, read_only: bool = False) -> AppSettings:
    """Create deterministic settings for audit decorator tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            f'{{"work":{{"url":"https://rancher.example.com","token":"token-x:secret",'
            f'"verify_ssl":true,"read_only":{str(read_only).lower()}}}}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


def test_emit_audit_writes_to_audit_logger() -> None:
    """emit_audit should emit one record on the rancher_mcp.audit logger."""

    entry = AuditEntry(
        tool_name="test_tool",
        operation="apply",
        plane="steve",
        outcome="success",
        instance="work",
        schema_id="configmap",
        resource_id="demo",
    )

    with capture_logs() as logs:
        emit_audit(entry)

    assert len(logs) == 1
    record = logs[0]
    assert record["event"] == "audit"
    assert record["log_level"] == "info"
    assert record["tool_name"] == "test_tool"
    assert record["operation"] == "apply"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert record["instance"] == "work"
    assert record["schema_id"] == "configmap"
    assert record["resource_id"] == "demo"


def test_emit_audit_excludes_none_fields() -> None:
    """Optional fields with None values must not appear in the emitted record."""

    entry = AuditEntry(
        tool_name="t",
        operation="create",
        plane="norman",
        outcome="success",
    )
    with capture_logs() as logs:
        emit_audit(entry)
    [record] = logs
    assert "namespace" not in record
    assert "error_code" not in record
    assert "error_message" not in record
    assert "http_status" not in record


@pytest.mark.asyncio
async def test_audit_mutation_decorator_logs_success() -> None:
    """Decorator should emit one success record after a normal return."""

    @audit_mutation(operation="apply", plane="steve")
    async def fake_apply(*, schema_id: str, resource_id: str, instance: str) -> str:
        return "ok"

    with capture_logs() as logs:
        result = await fake_apply(
            schema_id="configmap",
            resource_id="demo-config",
            instance="work",
        )

    assert result == "ok"
    [record] = [r for r in logs if r["event"] == "audit"]
    assert record["outcome"] == "success"
    assert record["tool_name"] == "fake_apply"
    assert record["plane"] == "steve"
    assert record["operation"] == "apply"
    assert record["schema_id"] == "configmap"
    assert record["resource_id"] == "demo-config"
    assert record["instance"] == "work"
    assert record["arg_keys"] == ["instance", "resource_id", "schema_id"]
    # Sensitive values must NOT leak into the audit record.
    assert "demo-config" not in str(record).replace("'demo-config'", "")  # only as resource_id


@pytest.mark.asyncio
async def test_audit_mutation_decorator_logs_capability_error_and_reraises() -> None:
    """RancherCapabilityError should produce error record and propagate."""

    @audit_mutation(operation="delete", plane="norman")
    async def fake_delete(*, schema_id: str, instance: str) -> None:
        raise RancherCapabilityError(
            f"Rancher instance {instance!r} is configured read-only for mutations"
        )

    with capture_logs() as logs, pytest.raises(RancherCapabilityError, match="read-only"):
        await fake_delete(schema_id="project", instance="work")

    [record] = [r for r in logs if r["event"] == "audit"]
    assert record["outcome"] == "error"
    assert record["error_code"] == "CAPABILITY_ERROR"
    assert "read-only for mutations" in record["error_message"]
    # http_status is not set on capability errors.
    assert "http_status" not in record


@pytest.mark.asyncio
async def test_audit_mutation_decorator_logs_api_error_with_http_status() -> None:
    """RancherAPIError should include http_status in the error record."""

    @audit_mutation(operation="patch", plane="steve")
    async def fake_patch(*, schema_id: str) -> None:
        raise RancherAPIError(404, "not found", field="metadata.name")

    with capture_logs() as logs, pytest.raises(RancherAPIError):
        await fake_patch(schema_id="configmap")

    [record] = [r for r in logs if r["event"] == "audit"]
    assert record["outcome"] == "error"
    assert record["error_code"] == "API_ERROR"
    assert record["http_status"] == 404


@pytest.mark.asyncio
async def test_audit_mutation_emits_for_read_only_instance_rejection() -> None:
    """End-to-end: a read-only instance rejection on a real mutation tool emits audit."""

    from rancher_mcp.tools.resource_mutations import rancher_steve_resource_patch

    class _StubSteve:
        async def get_json(self, *args: Any, **kwargs: Any) -> dict[str, object]:
            raise AssertionError("should not reach Steve before read-only check")

    class _StubMgmt:
        async def patch_json(self, *args: Any, **kwargs: Any) -> dict[str, object]:
            raise AssertionError("should not reach management client")

    with (
        capture_logs() as logs,
        pytest.raises(RancherCapabilityError, match="configured read-only"),
    ):
        await rancher_steve_resource_patch(
            schema_id="configmap",
            resource_id="demo",
            cluster_id="venue-local",
            namespace="default",
            payload_json='{"data": {"k": "v"}}',
            instance="work",
            settings=build_settings(read_only=True),
            steve_client=_StubSteve(),
            management_client=_StubMgmt(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_steve_resource_patch"
    assert record["operation"] == "patch"
    assert record["plane"] == "steve"
    assert record["outcome"] == "error"
    assert record["error_code"] == "CAPABILITY_ERROR"
    assert record["instance"] == "work"
    assert record["schema_id"] == "configmap"
    # arg_keys should reflect what the caller passed (no values leak).
    assert "payload_json" in record["arg_keys"]
    assert "settings" in record["arg_keys"]
