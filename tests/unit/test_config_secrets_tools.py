# ruff: noqa: S105, S106
"""Curated config-and-secrets tool tests (configmaps, secrets, service_accounts).

The S105/S106 noqa is intentional: this test file deliberately passes
arguments named ``secret_*`` and asserts on string values like ``"Opaque"``
that ruff's bandit-derived rules flag as possible hardcoded passwords.
"""

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.config_secrets import (
    rancher_config_map_apply,
    rancher_config_map_create,
    rancher_config_map_delete,
    rancher_config_map_get,
    rancher_config_maps_list,
    rancher_secret_create,
    rancher_secret_get,
    rancher_secrets_list,
    rancher_service_account_get,
    rancher_service_accounts_list,
)
from rancher_mcp.tools.config_secrets.shared import (
    build_configmap_payload,
    build_secret_payload,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated config_secrets tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_CONFIG_MAP_PAYLOAD = {
    "metadata": {
        "name": "demo-config",
        "namespace": "demo",
        "annotations": {"app.kubernetes.io/managed-by": "rancher"},
    },
    "data": {
        "config.yaml": "key: value",
        "extra.json": "{}",
    },
    "binaryData": {
        "blob.bin": "AAAA",
    },
    "immutable": False,
}

_SECRET_PAYLOAD = {
    "metadata": {
        "name": "demo-secret",
        "namespace": "demo",
        "annotations": {"app.kubernetes.io/managed-by": "rancher"},
    },
    "type": "Opaque",
    "data": {
        "password": "c2VjcmV0",
        "api-key": "Zm9vYmFy",
    },
    "immutable": True,
}

_SERVICE_ACCOUNT_PAYLOAD = {
    "metadata": {
        "name": "demo-sa",
        "namespace": "demo",
        "annotations": {"description": "demo service account"},
    },
    "secrets": [
        {"name": "demo-sa-token-abc"},
        {"name": "demo-sa-token-def"},
    ],
    "imagePullSecrets": [
        {"name": "regcred"},
    ],
    "automountServiceAccountToken": False,
}


class StubConfigSecretsClient:
    """Deterministic raw Kubernetes proxy client for curated config-secrets tools."""

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for write requests."""

        self.last_post_path: str | None = None
        self.last_post_payload: dict[str, object] | None = None
        self.last_put_path: str | None = None
        self.last_put_payload: dict[str, object] | None = None
        self.last_delete_path: str | None = None

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake raw Kubernetes core-API payloads."""

        cm_root = "/k8s/clusters/local/api/v1/namespaces/demo/configmaps"
        if path == cm_root:
            assert params == {"limit": 5}
            return {"items": [_CONFIG_MAP_PAYLOAD]}
        if path == f"{cm_root}/demo-config":
            assert params is None
            return _CONFIG_MAP_PAYLOAD

        sec_root = "/k8s/clusters/local/api/v1/namespaces/demo/secrets"
        if path == sec_root:
            assert params == {"limit": 5}
            return {"items": [_SECRET_PAYLOAD]}
        if path == f"{sec_root}/demo-secret":
            assert params is None
            return _SECRET_PAYLOAD

        sa_root = "/k8s/clusters/local/api/v1/namespaces/demo/serviceaccounts"
        if path == sa_root:
            assert params == {"limit": 5}
            return {"items": [_SERVICE_ACCOUNT_PAYLOAD]}
        if path == f"{sa_root}/demo-sa":
            assert params is None
            return _SERVICE_ACCOUNT_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")

    async def post_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the create request and echo a Kubernetes-shaped response.

        Echoes the request body as the API server would on success: the
        response payload IS the created resource. The stub augments the
        echoed payload with realistic post-create mutations (resourceVersion
        and uid) so the curated detail can be parsed end-to-end.
        """

        self.last_post_path = path
        assert payload is not None
        # Snapshot the outgoing request for assertions (a copy so the
        # caller can't mutate it after the fact).
        self.last_post_payload = dict(payload)

        cm_root = "/k8s/clusters/local/api/v1/namespaces/demo/configmaps"
        if path == cm_root:
            assert params is None
            response = dict(payload)
            metadata = dict(response.get("metadata") or {})  # type: ignore[arg-type]
            metadata["uid"] = "test-uid-1234"
            metadata["resourceVersion"] = "42"
            response["metadata"] = metadata
            return response

        sec_root = "/k8s/clusters/local/api/v1/namespaces/demo/secrets"
        if path == sec_root:
            assert params is None
            # The API server normalizes stringData → data (base64). The
            # stub mirrors that behavior so curated detail parsing works
            # against a realistic response shape.
            response = dict(payload)
            metadata = dict(response.get("metadata") or {})  # type: ignore[arg-type]
            metadata["uid"] = "test-secret-uid-5678"
            metadata["resourceVersion"] = "7"
            response["metadata"] = metadata
            string_data = response.pop("stringData", None)
            if isinstance(string_data, dict):
                # Naive "encoding" placeholder — what matters for the
                # test is that the data dict shape is correct, not the
                # specific base64 encoding.
                existing_data = response.get("data") or {}
                merged: dict[str, str] = {}
                if isinstance(existing_data, dict):
                    merged.update(existing_data)  # type: ignore[arg-type]
                # Use a fixed sentinel so tests can assert the response
                # shape doesn't carry the original plaintext values.
                for key in string_data:
                    merged[key] = "<encoded>"
                response["data"] = merged
            return response

        raise AssertionError(f"unexpected post path {path!r}")

    async def put_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the apply request and echo a Kubernetes-shaped response.

        Apply is HTTP PUT to the resource detail path. The API server
        echoes the resource as stored, with the resourceVersion bumped
        (apply mutates state). The stub mirrors that shape so the
        curated detail can be parsed end-to-end.
        """

        self.last_put_path = path
        assert payload is not None
        self.last_put_payload = dict(payload)

        cm_detail = "/k8s/clusters/local/api/v1/namespaces/demo/configmaps/demo-config"
        if path == cm_detail:
            assert params is None
            response = dict(payload)
            metadata = dict(response.get("metadata") or {})  # type: ignore[arg-type]
            metadata["uid"] = "test-uid-1234"
            metadata["resourceVersion"] = "99"
            response["metadata"] = metadata
            return response

        raise AssertionError(f"unexpected put path {path!r}")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Kubernetes Status object."""

        del payload  # unused for k8s configmap deletes
        self.last_delete_path = path

        cm_detail = "/k8s/clusters/local/api/v1/namespaces/demo/configmaps/demo-config"
        if path == cm_detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-config", "kind": "configmaps"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_config_maps_list_counts_data_and_binary_data() -> None:
    """List should count data and binary data keys without exposing values."""

    result = await rancher_config_maps_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    assert result.config_map_count == 1
    [cm] = result.config_maps
    assert cm.name == "demo-config"
    assert cm.data_key_count == 2
    assert cm.binary_data_key_count == 1
    assert cm.immutable is False


@pytest.mark.asyncio
async def test_rancher_config_map_get_includes_keys_and_payload() -> None:
    """Detail should include data_keys, binary_data_keys, annotations, and full payload."""

    result = await rancher_config_map_get(
        namespace="demo",
        config_map_name="demo-config",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    assert result.name == "demo-config"
    assert result.data_keys == ["config.yaml", "extra.json"]
    assert result.binary_data_keys == ["blob.bin"]
    assert result.annotation_keys == ["app.kubernetes.io/managed-by"]
    assert result.payload == _CONFIG_MAP_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_secrets_list_masks_values_and_exposes_type() -> None:
    """List should expose secret_type and key counts but never values."""

    result = await rancher_secrets_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    assert result.secret_count == 1
    [sec] = result.secrets
    assert sec.name == "demo-secret"
    assert sec.secret_type == "Opaque"
    assert sec.data_key_count == 2
    assert sec.immutable is True
    # Defensively: the typed summary must NOT carry data values.
    assert "data" not in sec.model_dump()


@pytest.mark.asyncio
async def test_rancher_secrets_list_filters_by_type() -> None:
    """secret_type filter should drop entries whose type doesn't match."""

    result = await rancher_secrets_list(
        namespace="demo",
        cluster_id="local",
        secret_type="kubernetes.io/dockerconfigjson",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    assert result.secret_count == 0
    assert result.secrets == []


@pytest.mark.asyncio
async def test_rancher_secret_get_omits_payload_field() -> None:
    """Detail must expose data_keys but never the data values, and lack a payload field."""

    result = await rancher_secret_get(
        namespace="demo",
        secret_name="demo-secret",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubConfigSecretsClient(),
    )

    assert result.name == "demo-secret"
    assert result.secret_type == "Opaque"
    assert result.data_key_count == 2
    assert result.data_keys == ["api-key", "password"]
    assert result.annotation_keys == ["app.kubernetes.io/managed-by"]
    # Critical mask check: serialized output must NOT contain a payload field.
    dumped = result.model_dump()
    assert "payload" not in dumped
    # And no raw base64 values.
    assert "c2VjcmV0" not in str(dumped)
    assert "Zm9vYmFy" not in str(dumped)


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
# build_configmap_payload composer (pure-function unit tests)
# =====================================================================


def test_build_configmap_payload_minimal_required_fields() -> None:
    """Composer with only required args produces a Kubernetes-shaped POST body."""

    payload = build_configmap_payload(
        name="demo-config",
        namespace="demo",
        data={"key": "value"},
    )

    assert payload == {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "demo-config", "namespace": "demo"},
        "data": {"key": "value"},
    }


def test_build_configmap_payload_omits_none_optional_fields() -> None:
    """Composer must NOT emit binaryData/immutable/labels/annotations when None.

    Sending those keys with empty/null values changes Kubernetes
    apply-merge semantics — the composer's contract is that None
    means "don't touch this field on the server".
    """

    payload = build_configmap_payload(
        name="demo-config",
        namespace="demo",
        data={"key": "value"},
        binary_data=None,
        immutable=None,
        labels=None,
        annotations=None,
    )

    assert payload == {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "demo-config", "namespace": "demo"},
        "data": {"key": "value"},
    }
    assert "binaryData" not in payload
    assert "immutable" not in payload


def test_build_configmap_payload_includes_optional_fields_when_set() -> None:
    """Composer wires optional args into the right payload slots when set."""

    payload = build_configmap_payload(
        name="demo-config",
        namespace="demo",
        data={"k": "v"},
        binary_data={"b": "AAAA"},
        immutable=True,
        labels={"app": "demo"},
        annotations={"owner": "ops"},
    )

    assert payload == {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": "demo-config",
            "namespace": "demo",
            "labels": {"app": "demo"},
            "annotations": {"owner": "ops"},
        },
        "data": {"k": "v"},
        "binaryData": {"b": "AAAA"},
        "immutable": True,
    }


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


# =====================================================================
# build_secret_payload composer tests
# =====================================================================


def test_build_secret_payload_with_string_data_only() -> None:
    """Plaintext string_data goes into stringData; data field omitted."""

    payload = build_secret_payload(
        name="demo-secret",
        namespace="demo",
        string_data={"password": "hunter2"},
    )

    assert payload == {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "demo-secret", "namespace": "demo"},
        "stringData": {"password": "hunter2"},
    }
    # data field is NOT in the payload when only string_data is given.
    assert "data" not in payload


def test_build_secret_payload_with_data_only_and_secret_type() -> None:
    """Already-base64 data goes into `data`; stringData omitted."""

    payload = build_secret_payload(
        name="demo-secret",
        namespace="demo",
        data={"password": "aHVudGVyMg=="},
        secret_type="kubernetes.io/dockerconfigjson",
        immutable=True,
    )

    assert payload == {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "demo-secret", "namespace": "demo"},
        "data": {"password": "aHVudGVyMg=="},
        "type": "kubernetes.io/dockerconfigjson",
        "immutable": True,
    }
    assert "stringData" not in payload


def test_build_secret_payload_refuses_when_both_data_sources_empty() -> None:
    """Composer rejects empty payloads — secrets must store at least one entry."""

    with pytest.raises(ValueError, match="non-empty"):
        build_secret_payload(name="x", namespace="demo")


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
