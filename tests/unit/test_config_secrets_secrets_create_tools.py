# ruff: noqa: S105, S106
"""Curated Secret write tool tests (create)."""

from __future__ import annotations

import pytest
from _config_secrets_support import StubConfigSecretsClient, build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.config_secrets import (
    rancher_secret_create,
)

# Synthetic fixture values, not credentials. Bound once so the literals live on
# a single line that both `detect-secrets` (allowlisted here) and ruff's line
# limit are happy with — inlining them wraps across lines, which moves the
# pragma off the flagged token and re-trips the hook.
_STRING_DATA = {"password": "hunter2", "api-key": "abc123"}  # pragma: allowlist secret
_B64_DATA = {"password": "aHVudGVyMg=="}  # pragma: allowlist secret
_SECRET_NAME = "demo-secret"  # pragma: allowlist secret

# =====================================================================
# rancher_secret_create end-to-end tests
# =====================================================================


@pytest.mark.asyncio
async def test_rancher_secret_create_round_trips_string_data() -> None:
    """Secret create POSTs the typed payload and returns a masked detail.

    The curated detail must NOT carry a `payload` field — secret values
    never round-trip back to the agent. data_keys is the only safe
    surface for what's in the secret.
    """

    reset_rate_limit_state()
    client = StubConfigSecretsClient()

    result = await rancher_secret_create(
        namespace="demo",
        secret_name=_SECRET_NAME,
        string_data=_STRING_DATA,
        secret_type="Opaque",  # pragma: allowlist secret — a k8s type name
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Request lands at the secrets collection path.
    assert client.last_post_path == "/k8s/clusters/local/api/v1/namespaces/demo/secrets"

    # Outgoing payload carries stringData (not data) — composer chose
    # the right path based on which arg the caller provided.
    sent = client.last_post_payload
    assert sent is not None
    assert sent["kind"] == "Secret"
    assert sent["stringData"] == _STRING_DATA
    assert sent["type"] == "Opaque"
    assert "data" not in sent

    # CRITICAL masking checks — the curated detail must not expose
    # plaintext values, and must not have a `payload` field at all.
    assert result.name == _SECRET_NAME
    assert result.data_key_count == 2
    # data_keys lists the key names only (alphabetically).
    assert result.data_keys == ["api-key", "password"]
    dumped = result.model_dump()
    # No payload field on the detail — masked-by-design.
    assert "payload" not in dumped
    # And no plaintext values anywhere in the serialized output.
    assert "hunter2" not in str(dumped)
    assert "abc123" not in str(dumped)


@pytest.mark.asyncio
async def test_rancher_secret_create_audit_captures_arg_names_only() -> None:
    """Audit captures string_data as an arg NAME — the value never appears.

    This is the most security-sensitive test for the substrate: even
    when the agent passes plaintext secret values, the audit log must
    only carry the arg key (`string_data`), never the dict contents.
    """

    reset_rate_limit_state()

    sentinel = "PLAINTEXT-SENTINEL-9d8e7f6"

    with capture_logs() as logs:
        await rancher_secret_create(
            namespace="demo",
            secret_name=_SECRET_NAME,
            string_data={"super-secret": sentinel},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubConfigSecretsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_secret_create"
    assert record["operation"] == "secret_create"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    # arg_keys contains the parameter NAME but no values.
    assert "string_data" in record["arg_keys"]
    assert "secret_name" in record["arg_keys"]
    # The plaintext sentinel must NOT appear anywhere in the record.
    assert sentinel not in str(record)


@pytest.mark.asyncio
async def test_rancher_secret_create_with_data_arg_skips_string_data() -> None:
    """When caller passes `data` (already-base64), composer omits stringData."""

    reset_rate_limit_state()
    client = StubConfigSecretsClient()

    await rancher_secret_create(
        namespace="demo",
        secret_name=_SECRET_NAME,
        data=_B64_DATA,
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    sent = client.last_post_payload
    assert sent is not None
    assert sent["data"] == _B64_DATA
    assert "stringData" not in sent
