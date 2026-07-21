"""M-SEC: sensitive singular GETs reveal real values; list stays redacted; reveal is audited."""

from __future__ import annotations

import base64
import contextlib
from typing import Any

import structlog

from rancher_mcp.audit import _wrap_reveal_audit, apply_sensitive_reveal_audit
from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.config_secrets import (
    RancherSecretDetail,
    RancherSecretSummary,
    _decode_secret_data,
)
from rancher_mcp.models.fleet_registration.cluster_registration_tokens import (
    RancherClusterRegistrationTokenDetail,
)


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def test_secret_get_reveals_decoded_data() -> None:
    detail = RancherSecretDetail.model_validate(
        {
            "metadata": {"name": "app", "namespace": "default"},
            "type": "Opaque",
            "data": {
                "message": _b64("hunter2"),
                "user": _b64("admin"),
            },
        }
    )
    dumped = detail.model_dump(by_alias=True)
    assert dumped["data"] == {"message": "hunter2", "user": "admin"}  # revealed, decoded


def test_reveal_skips_scrub_even_for_credential_named_keys() -> None:
    # `clientSecret` is on the scrub denylist; the reveal model must still show it,
    # and must NOT stamp the `redacted` marker (scrub is skipped entirely).
    detail = RancherSecretDetail.model_validate(
        {
            "metadata": {"name": "x", "namespace": "n"},
            "type": "Opaque",
            "data": {"clientSecret": _b64("s3cr3t-value")},  # pragma: allowlist secret
        }
    )
    dumped = detail.model_dump(by_alias=True)
    assert dumped["data"]["clientSecret"] == "s3cr3t-value"  # pragma: allowlist secret
    assert "redacted" not in dumped


def test_secrets_list_summary_never_carries_values() -> None:
    summary = RancherSecretSummary.model_validate(
        {
            "metadata": {"name": "x", "namespace": "n"},
            "data": {"password": _b64("nope")},
        }  # pragma: allowlist secret
    )
    dumped = summary.model_dump(by_alias=True)
    assert "data" not in dumped  # the browse surface has no values field at all


def test_reveal_flag_off_by_default_on_the_base_and_summary() -> None:
    assert RancherModel.serializer_reveals_secrets is False
    assert RancherSecretSummary.serializer_reveals_secrets is False
    assert RancherSecretDetail.serializer_reveals_secrets is True
    assert RancherClusterRegistrationTokenDetail.serializer_reveals_secrets is True


def test_decode_secret_data_utf8_and_binary_fallback() -> None:
    binary_b64 = base64.b64encode(b"\xff\xfe\x00").decode()
    out = _decode_secret_data({"txt": _b64("hi"), "bin": binary_b64})
    assert out["txt"] == "hi"
    assert out["bin"] == binary_b64  # non-UTF-8 → raw base64 kept unchanged
    assert _decode_secret_data("not-a-dict") == {}
    assert _decode_secret_data({"k": 123}) == {}  # non-str value skipped


async def test_reveal_is_audited_identity_only() -> None:
    async def fake_get(**_kwargs: Any) -> str:
        return "the-decoded-secret-value"

    wrapped = _wrap_reveal_audit(fake_get, "rancher_secret_get", "steve", "secret_name")
    target = "app"
    with structlog.testing.capture_logs() as logs:
        result = await wrapped(
            instance="prod", cluster_id="local", namespace="default", secret_name=target
        )

    assert result == "the-decoded-secret-value"
    reveals = [e for e in logs if e.get("operation") == "reveal"]
    assert len(reveals) == 1
    entry = reveals[0]
    assert entry["tool_name"] == "rancher_secret_get"
    assert entry["resource_id"] == "app"
    assert entry["namespace"] == "default"
    assert entry["outcome"] == "success"
    # the value itself is never in the audit record
    assert "the-decoded-secret-value" not in str(entry)


async def test_failed_reveal_emits_no_record() -> None:
    async def failing_get(**_kwargs: Any) -> str:
        raise RuntimeError("not found")

    wrapped = _wrap_reveal_audit(failing_get, "rancher_secret_get", "steve", "secret_name")
    target = "ghost"
    with structlog.testing.capture_logs() as logs, contextlib.suppress(RuntimeError):
        await wrapped(secret_name=target)
    assert [e for e in logs if e.get("operation") == "reveal"] == []


def test_apply_wraps_only_the_reveal_tools() -> None:
    async def _noop(**_kwargs: Any) -> None:
        return None

    class _Tool:
        def __init__(self, name: str) -> None:
            self.name = name
            self.fn = _noop

    class _Mgr:
        def __init__(self) -> None:
            self._tools = {
                "rancher_secret_get": _Tool("rancher_secret_get"),
                "rancher_cluster_registration_token_get": _Tool(
                    "rancher_cluster_registration_token_get"
                ),
                "rancher_clusters_list": _Tool("rancher_clusters_list"),
            }

    class _Mcp:
        def __init__(self) -> None:
            self._tool_manager = _Mgr()

    mcp = _Mcp()
    untouched = mcp._tool_manager._tools["rancher_clusters_list"].fn
    secret_before = mcp._tool_manager._tools["rancher_secret_get"].fn
    apply_sensitive_reveal_audit(mcp)
    assert mcp._tool_manager._tools["rancher_clusters_list"].fn is untouched
    assert mcp._tool_manager._tools["rancher_secret_get"].fn is not secret_before
    assert (
        mcp._tool_manager._tools["rancher_cluster_registration_token_get"].fn.__wrapped__  # type: ignore[attr-defined]
        is not None
    )
