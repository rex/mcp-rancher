"""M-SEC / M-SEC-2: the singular sensitive GETs gate their real-value reveal
behind an explicit parameter; list always stays redacted; only an actual
reveal (not a names-only get) is audited."""

from __future__ import annotations

import base64
import contextlib
from typing import Any

import structlog
from _config_secrets_support import StubConfigSecretsClient, build_settings

from rancher_mcp.audit import _REVEAL_TOOLS, _wrap_reveal_audit, apply_sensitive_reveal_audit
from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.config_secrets import (
    RancherSecretDetail,
    RancherSecretSummary,
    _decode_secret_data,
)
from rancher_mcp.models.fleet_registration.cluster_registration_tokens import (
    RancherClusterRegistrationTokenDetail,
)
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.config_secrets import rancher_secret_create, rancher_secret_get


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def test_secret_get_reveals_decoded_data() -> None:
    """The MODEL always decodes `data` on ``model_validate`` — it is the
    generated tool layer (see the `test_secret_get_default_*` /
    `test_secret_get_reveal_true_*` tests below) that gates whether a caller
    ever sees the decoded values by default (M-SEC-2)."""

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


# =====================================================================
# M-SEC-2: the generated `rancher_secret_get` tool gates the reveal behind
# an explicit `reveal` parameter. `_SECRET_PAYLOAD` (in
# `_config_secrets_support.py`) base64-decodes to
# {"password": "secret", "api-key": "foobar"}.  # pragma: allowlist secret
# =====================================================================


async def test_secret_get_default_omits_data_but_keeps_data_keys() -> None:
    """Default call (`reveal` omitted → False): no `data` values ship, but
    `dataKeys` (names) is still populated — AE-01-clean by default."""

    result = await rancher_secret_get(
        namespace="demo",
        secret_name="demo-secret",  # pragma: allowlist secret
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    dumped = result.model_dump(by_alias=True)
    assert "data" not in dumped  # suppressed to {}, dropped by the L-0 envelope
    assert dumped["dataKeys"] == ["api-key", "password"]
    # the decoded "api-key" value never appears anywhere in the dump. (Can't
    # canary the decoded "password" value the same way: it decodes to
    # "secret", a substring of the legitimate resource name "demo-secret".)
    assert "foobar" not in str(dumped)


async def test_secret_get_reveal_true_returns_decoded_values() -> None:
    """`reveal=True` returns the decoded values — and `password` (on the
    scrub denylist) coming through unredacted proves `serializer_reveals_secrets`
    still skips the scrub for this revealed shape."""

    result = await rancher_secret_get(
        namespace="demo",
        secret_name="demo-secret",  # pragma: allowlist secret
        cluster_id="local",
        reveal=True,
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    dumped = result.model_dump(by_alias=True)
    assert dumped["data"] == {"password": "secret", "api-key": "foobar"}  # pragma: allowlist secret
    assert dumped["dataKeys"] == ["api-key", "password"]


async def test_secret_create_never_emits_values_no_reveal_input() -> None:
    """`secret_create` has no `reveal` parameter at all — it must ALWAYS
    suppress `data`, matching `secret_get`'s default (never its `reveal=True`
    path). Regression guard for the M-SEC-era leak M-SEC-2 closes: create
    reuses get's response-shaping pipeline, and previously nothing overrode
    `data`, so whatever the payload decoded to rode along unmasked."""

    reset_rate_limit_state()
    result = await rancher_secret_create(
        namespace="demo",
        secret_name="new-secret",  # pragma: allowlist secret
        string_data={"password": "hunter2"},  # pragma: allowlist secret
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    dumped = result.model_dump(by_alias=True)
    assert "data" not in dumped  # suppressed to {}, dropped by the L-0 envelope
    assert dumped["dataKeys"] == ["password"]


async def test_reveal_is_audited_identity_only() -> None:
    """No `gate_kwarg` passed → unconditional audit (the original M-SEC
    behavior; still exactly how `cluster_registration_token_get` is wired)."""

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


async def test_secret_get_audit_fires_only_on_reveal_true() -> None:
    """M-SEC-2: with `gate_kwarg="reveal"` wired (as `secret_get` is in
    production), a names-only call — `reveal` omitted or explicitly False —
    must NOT be logged as a credential reveal; only `reveal=True` is."""

    async def fake_get(**_kwargs: Any) -> str:
        return "the-decoded-secret-value"

    wrapped = _wrap_reveal_audit(
        fake_get, "rancher_secret_get", "steve", "secret_name", gate_kwarg="reveal"
    )
    target = "app"

    with structlog.testing.capture_logs() as logs:
        await wrapped(secret_name=target, namespace="default", reveal=False)
        await wrapped(secret_name=target, namespace="default")  # reveal omitted entirely
    assert [e for e in logs if e.get("operation") == "reveal"] == []

    with structlog.testing.capture_logs() as logs:
        await wrapped(secret_name=target, namespace="default", reveal=True)
    reveals = [e for e in logs if e.get("operation") == "reveal"]
    assert len(reveals) == 1
    assert reveals[0]["resource_id"] == "app"
    assert "the-decoded-secret-value" not in str(reveals[0])


def test_reveal_tools_registry_gates_secret_get_not_registration_token() -> None:
    """`secret_get` is gated on its own `reveal` kwarg; `cluster_registration_token_get`
    keeps its unconditional (gate=None) M-SEC audit — unchanged, out of scope for M-SEC-2."""

    assert _REVEAL_TOOLS["rancher_secret_get"] == ("steve", "secret_name", "reveal")
    assert _REVEAL_TOOLS["rancher_cluster_registration_token_get"] == (
        "management",
        "cluster_registration_token_id",
        None,
    )


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
