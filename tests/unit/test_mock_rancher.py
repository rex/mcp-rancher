"""Tests for the fixture-backed mock Rancher server."""

from __future__ import annotations

import json

from devtools.mock_rancher import MockRancherState


def _json_body(response_body: bytes) -> dict[str, object]:
    payload = json.loads(response_body.decode("utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_mock_rancher_login_returns_bearer_token() -> None:
    """Correct mock credentials should return the configured token."""

    state = MockRancherState()
    response = state.handle(
        "POST",
        "/v3-public/localProviders/local?action=login",
        {},
        b'{"username":"admin","password":"admin"}',
    )

    assert response.status_code == 200
    assert _json_body(response.body) == {"token": "token-mock:secret", "type": "token"}


def test_mock_rancher_requires_bearer_auth_after_login() -> None:
    """Non-login routes should reject requests without the configured bearer token."""

    state = MockRancherState()
    response = state.handle("GET", "/v3", {}, b"")

    assert response.status_code == 401
    assert _json_body(response.body)["message"] == "unauthorized"


def test_mock_rancher_serves_health_and_version_with_valid_token() -> None:
    """The mock should expose the basic discovery endpoints used in provider validation."""

    state = MockRancherState()
    headers = {"Authorization": "Bearer token-mock:secret"}

    health = state.handle("GET", "/healthz", headers, b"")
    version = state.handle("GET", "/v3/settings/server-version", headers, b"")

    assert health.status_code == 200
    assert health.body == b"ok\n"
    assert version.status_code == 200
    assert _json_body(version.body)["value"] == "v2.6.5"


def test_mock_rancher_serves_schema_lists_and_local_alias_routes() -> None:
    """The mock should synthesize schema collections and alias local Steve paths."""

    state = MockRancherState()
    headers = {"Authorization": "Bearer token-mock:secret"}

    schema_list = state.handle("GET", "/v1/schemas", headers, b"")
    namespace = state.handle("GET", "/v1/schemas/namespace", headers, b"")

    assert schema_list.status_code == 200
    assert _json_body(schema_list.body)["type"] == "collection"
    assert namespace.status_code == 200
    assert _json_body(namespace.body)["id"] == "namespace"
