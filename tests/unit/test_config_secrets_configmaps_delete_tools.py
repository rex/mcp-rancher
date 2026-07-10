"""Curated ConfigMap delete tool tests."""

from __future__ import annotations

import pytest
from _config_secrets_support import StubConfigSecretsClient, build_settings
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.config_secrets import rancher_config_map_delete

# =====================================================================
# rancher_config_map_delete end-to-end tests
# =====================================================================


@pytest.mark.asyncio
async def test_rancher_config_map_delete_requires_exact_confirmation_phrase() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call.

    The whole point of the confirmation phrase is that an agent (or
    user) can't accidentally delete a resource by guessing the tool's
    contract. The exact phrase must be echoed back.
    """

    reset_rate_limit_state()
    client = StubConfigSecretsClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_config_map_delete(
            namespace="demo",
            config_map_name="demo-config",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call.
    assert "delete configmap demo-config in namespace demo" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_config_map_delete_with_correct_phrase_succeeds() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubConfigSecretsClient()

    result = await rancher_config_map_delete(
        namespace="demo",
        config_map_name="demo-config",
        confirmation="delete configmap demo-config in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert (
        client.last_delete_path
        == "/k8s/clusters/local/api/v1/namespaces/demo/configmaps/demo-config"
    )
    assert result.deleted is True
    assert result.resource_kind == "config_map"
    assert result.resource_name == "demo-config"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == ("delete configmap demo-config in namespace demo")
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_config_maps_list"]


@pytest.mark.asyncio
async def test_rancher_config_map_delete_emits_audit_with_delete_op() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_config_map_delete(
            namespace="demo",
            config_map_name="demo-config",
            confirmation="delete configmap demo-config in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubConfigSecretsClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "configmap_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_config_map_delete(
            namespace="demo",
            config_map_name="demo-config",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubConfigSecretsClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "configmap_delete"
    assert reject_audits[0]["outcome"] == "error"
    # Audit captures the rejection reason but never the wrong phrase value.
    assert "bad" not in reject_audits[0].get("arg_keys", [])


@pytest.mark.asyncio
async def test_rancher_config_map_delete_refuses_read_only_instance() -> None:
    """Read-only instances must refuse delete even with valid confirmation.

    The order of checks matters: confirmation guard runs FIRST (so an
    agent on a read-only instance who hasn't even formed a valid phrase
    learns about the phrase requirement), then the read-only guard.
    With a valid phrase, the read-only check then fires.
    """

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
        await rancher_config_map_delete(
            namespace="demo",
            config_map_name="demo-config",
            confirmation="delete configmap demo-config in namespace demo",
            cluster_id="local",
            instance="locked",
            settings=read_only_settings,
            client=StubConfigSecretsClient(),
        )
