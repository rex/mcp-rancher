# ruff: noqa: S105, S106
"""Shared setup for the curated config-and-secrets tool test suites.

Extracted from ``test_config_secrets_tools.py`` when it was split by
resource/operation to stay under the architecture line limit.
``build_settings``, the read-path payload constants, and the shared read
stub ``StubConfigSecretsClient`` are consumed by multiple config_secrets
test modules; operation-specific stubs stay with the tests that use them.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


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

        del payload  # unused for k8s configmap/secret deletes
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

        sec_detail = "/k8s/clusters/local/api/v1/namespaces/demo/secrets/demo-secret"
        if path == sec_detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-secret", "kind": "secrets"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")
