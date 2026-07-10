# ruff: noqa: S105, S106
"""Curated Secret write tool tests (create, delete)."""

from __future__ import annotations

import pytest
from _config_secrets_support import StubConfigSecretsClient, build_settings
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.config_secrets import (
    rancher_secret_create,
    rancher_secret_delete,
)

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
        secret_name="demo-secret",
        string_data={"password": "hunter2", "api-key": "abc123"},
        secret_type="Opaque",
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
    assert sent["stringData"] == {"password": "hunter2", "api-key": "abc123"}
    assert sent["type"] == "Opaque"
    assert "data" not in sent

    # CRITICAL masking checks — the curated detail must not expose
    # plaintext values, and must not have a `payload` field at all.
    assert result.name == "demo-secret"
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
            secret_name="demo-secret",
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
        secret_name="demo-secret",
        data={"password": "aHVudGVyMg=="},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    sent = client.last_post_payload
    assert sent is not None
    assert sent["data"] == {"password": "aHVudGVyMg=="}
    assert "stringData" not in sent


# =====================================================================
# rancher_secret_delete end-to-end tests
# =====================================================================


@pytest.mark.asyncio
async def test_rancher_secret_delete_requires_exact_confirmation_phrase() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubConfigSecretsClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_secret_delete(
            namespace="demo",
            secret_name="demo-secret",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete secret demo-secret in namespace demo" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_secret_delete_with_correct_phrase_succeeds() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubConfigSecretsClient()

    result = await rancher_secret_delete(
        namespace="demo",
        secret_name="demo-secret",
        confirmation="delete secret demo-secret in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert (
        client.last_delete_path == "/k8s/clusters/local/api/v1/namespaces/demo/secrets/demo-secret"
    )
    assert result.deleted is True
    assert result.resource_kind == "secret"
    assert result.resource_name == "demo-secret"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete secret demo-secret in namespace demo"
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_secrets_list"]


@pytest.mark.asyncio
async def test_rancher_secret_delete_emits_audit_with_delete_op() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_secret_delete(
            namespace="demo",
            secret_name="demo-secret",
            confirmation="delete secret demo-secret in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubConfigSecretsClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "secret_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_secret_delete(
            namespace="demo",
            secret_name="demo-secret",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubConfigSecretsClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "secret_delete"
    assert reject_audits[0]["outcome"] == "error"


@pytest.mark.asyncio
async def test_rancher_secret_delete_refuses_read_only_instance() -> None:
    """Read-only instances must refuse delete even with valid confirmation."""

    reset_rate_limit_state()
    read_only_settings = AppSettings(
        RANCHER_DEFAULT_INSTANCE="locked",
        RANCHER_INSTANCES_JSON=(
            '{"locked":{"url":"https://rancher.example.com","token":"token-x:secret",'
            '"verify_ssl":true,"read_only":true}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )

    with pytest.raises(RancherCapabilityError):
        await rancher_secret_delete(
            namespace="demo",
            secret_name="demo-secret",
            confirmation="delete secret demo-secret in namespace demo",
            cluster_id="local",
            instance="locked",
            settings=read_only_settings,
            client=StubConfigSecretsClient(),
        )
