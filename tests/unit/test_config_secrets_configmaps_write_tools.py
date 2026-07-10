"""Curated ConfigMap write tool tests (create, apply)."""

from __future__ import annotations

import pytest
from _config_secrets_support import StubConfigSecretsClient, build_settings
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.config_secrets import (
    rancher_config_map_apply,
    rancher_config_map_create,
)

# =====================================================================
# rancher_config_map_create end-to-end tests
# =====================================================================


@pytest.mark.asyncio
async def test_rancher_config_map_create_round_trips_request_and_response() -> None:
    """Create should POST a Kubernetes-shaped body and parse the echoed response."""

    reset_rate_limit_state()
    client = StubConfigSecretsClient()

    result = await rancher_config_map_create(
        namespace="demo",
        config_map_name="demo-config",
        data={"key": "value", "extra": "x"},
        labels={"app": "demo"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Request shape: composer-built POST body landed at the right path.
    assert client.last_post_path == "/k8s/clusters/local/api/v1/namespaces/demo/configmaps"
    assert client.last_post_payload == {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": "demo-config",
            "namespace": "demo",
            "labels": {"app": "demo"},
        },
        "data": {"key": "value", "extra": "x"},
    }

    # Response shape: same curated detail an agent would get from `get`,
    # including the post-create resourceVersion / uid the API server adds.
    assert result.name == "demo-config"
    assert result.data_key_count == 2
    assert result.data_keys == ["extra", "key"]
    assert result.suggested_next_steps == [
        "rancher_config_map_get",
        "rancher_pods_list",
    ]
    assert result.payload is not None
    response_metadata = result.payload["metadata"]
    assert isinstance(response_metadata, dict)
    assert response_metadata["uid"] == "test-uid-1234"
    assert response_metadata["resourceVersion"] == "42"


@pytest.mark.asyncio
async def test_rancher_config_map_create_omits_optional_args_from_request() -> None:
    """Optional args left as None must not appear in the request body."""

    reset_rate_limit_state()
    client = StubConfigSecretsClient()

    await rancher_config_map_create(
        namespace="demo",
        config_map_name="demo-config",
        data={"only": "data"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    sent = client.last_post_payload
    assert sent is not None
    assert "binaryData" not in sent
    assert "immutable" not in sent
    metadata = sent.get("metadata") or {}
    assert isinstance(metadata, dict)
    assert "labels" not in metadata
    assert "annotations" not in metadata


@pytest.mark.asyncio
async def test_rancher_config_map_create_refuses_read_only_instance() -> None:
    """Read-only instances must reject create with a capability error.

    The audit decorator is OUTER, so the rejection still produces an
    audit record (outcome=error, error_code=CAPABILITY_REQUIRED) before
    the exception propagates — this verifies both the gate AND the
    audit trail for refused writes.
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

    with capture_logs() as logs, pytest.raises(RancherCapabilityError):
        await rancher_config_map_create(
            namespace="demo",
            config_map_name="demo-config",
            data={"key": "value"},
            cluster_id="local",
            instance="locked",
            settings=read_only_settings,
            client=StubConfigSecretsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_config_map_create"
    assert record["operation"] == "configmap_create"
    assert record["plane"] == "steve"
    assert record["outcome"] == "error"
    assert record["instance"] == "locked"


@pytest.mark.asyncio
async def test_rancher_config_map_create_emits_success_audit() -> None:
    """A successful create writes one outcome=success audit record."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_config_map_create(
            namespace="demo",
            config_map_name="demo-config",
            data={"key": "value"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubConfigSecretsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_config_map_create"
    assert record["operation"] == "configmap_create"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert record["instance"] == "work"
    assert record["namespace"] == "demo"
    assert record["cluster_id"] == "local"
    # Audit captures arg NAMES, never values — verify the value strings
    # don't show up anywhere in the record.
    assert "value" not in str(record)
    # And the arg-name list is present and sorted.
    assert "data" in record["arg_keys"]
    assert "config_map_name" in record["arg_keys"]
    assert record["arg_keys"] == sorted(record["arg_keys"])


# =====================================================================
# rancher_config_map_apply end-to-end tests
# =====================================================================


@pytest.mark.asyncio
async def test_rancher_config_map_apply_uses_put_to_detail_path() -> None:
    """Apply must PUT (not POST) to the resource detail path with full state.

    Distinct from create which POSTs to the collection. Apply replaces
    the resource in place; the response carries a bumped resourceVersion.
    """

    reset_rate_limit_state()
    client = StubConfigSecretsClient()

    result = await rancher_config_map_apply(
        namespace="demo",
        config_map_name="demo-config",
        data={"key": "new-value"},
        immutable=True,
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # The verb went to the DETAIL path, not the collection path.
    assert (
        client.last_put_path == "/k8s/clusters/local/api/v1/namespaces/demo/configmaps/demo-config"
    )
    # POST capture stays empty — apply does NOT call create.
    assert client.last_post_path is None

    # Same composer as create produces the same payload shape.
    assert client.last_put_payload == {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "demo-config", "namespace": "demo"},
        "data": {"key": "new-value"},
        "immutable": True,
    }

    # Response is shaped through get's pipeline — same curated detail.
    assert result.name == "demo-config"
    assert result.data_keys == ["key"]
    assert result.immutable is True
    assert result.suggested_next_steps == [
        "rancher_config_map_get",
        "rancher_pods_list",
    ]


@pytest.mark.asyncio
async def test_rancher_config_map_apply_emits_success_audit_with_apply_op() -> None:
    """Apply audit records carry operation=configmap_apply (not _create)."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_config_map_apply(
            namespace="demo",
            config_map_name="demo-config",
            data={"key": "value"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubConfigSecretsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_config_map_apply"
    assert record["operation"] == "configmap_apply"
    assert record["outcome"] == "success"
