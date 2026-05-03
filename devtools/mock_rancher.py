"""Fixture-backed mock Rancher server for local MCP-provider validation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import parse_qsl, urlparse

DEFAULT_FIXTURE_DIR = Path("tests/fixtures/rancher_2_6_5")
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"  # noqa: S105 - deterministic mock-only credential
DEFAULT_TOKEN = "token-mock:secret"  # noqa: S105 - deterministic mock-only token
DEFAULT_CLUSTER_ID = "venue-local"
DEFAULT_VERSION = "v2.6.5"

QueryKey = tuple[tuple[str, str], ...]
RouteKey = tuple[str, QueryKey]


@dataclass(frozen=True)
class MockResponse:
    """Minimal typed HTTP response."""

    status_code: int
    content_type: str
    body: bytes


class MockRancherState:
    """Fixture-backed request router with simple auth semantics."""

    def __init__(
        self,
        fixture_dir: Path = DEFAULT_FIXTURE_DIR,
        *,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
        token: str = DEFAULT_TOKEN,
        cluster_id: str = DEFAULT_CLUSTER_ID,
        rancher_version: str = DEFAULT_VERSION,
    ) -> None:
        self.fixture_dir = fixture_dir
        self.username = username
        self.password = password
        self.token = token
        self.cluster_id = cluster_id
        self.rancher_version = rancher_version
        self._routes, self._fixture_names = self._load_fixture_routes()
        self._norman_schema_list = self._schema_list("norman_schema_", "/v3/schemas")
        self._steve_schema_list = self._schema_list("steve_schema_", "/v1/schemas")

    def handle(
        self,
        method: str,
        target: str,
        headers: Mapping[str, str],
        body: bytes,
    ) -> MockResponse:
        """Resolve one mock Rancher request."""

        parsed = urlparse(target)
        query = self._normalize_query(parsed.query)
        if method == "POST" and parsed.path == "/v3-public/localProviders/local":
            return self._login_response(query, body)

        auth = headers.get("Authorization", "")
        if auth != f"Bearer {self.token}":
            return self._json_response(HTTPStatus.UNAUTHORIZED, {"message": "unauthorized"})

        if method == "GET" and parsed.path == "/healthz":
            return MockResponse(HTTPStatus.OK, "text/plain; charset=utf-8", b"ok\n")
        if method == "GET" and parsed.path == "/v3":
            return self._json_response(HTTPStatus.OK, self._norman_root())
        if method == "GET" and parsed.path in {"/v1", f"/k8s/clusters/{self.cluster_id}/v1"}:
            return self._json_response(HTTPStatus.OK, self._steve_root(parsed.path))
        if method == "GET" and parsed.path == "/v3/settings/server-version":
            return self._json_response(
                HTTPStatus.OK,
                {"type": "setting", "id": "server-version", "value": self.rancher_version},
            )
        if method == "GET" and parsed.path == "/v3/schemas":
            return self._json_response(HTTPStatus.OK, self._norman_schema_list)
        if method == "GET" and parsed.path in {
            "/v1/schemas",
            f"/k8s/clusters/{self.cluster_id}/v1/schemas",
        }:
            return self._json_response(HTTPStatus.OK, self._steve_schema_list)

        route = self._routes.get((parsed.path, query))
        if route is None and parsed.path.startswith("/v1/"):
            alias = parsed.path.replace("/v1/", f"/k8s/clusters/{self.cluster_id}/v1/", 1)
            route = self._routes.get((alias, query))
        if route is not None and method == "GET":
            return self._json_response(HTTPStatus.OK, route)

        return self._json_response(
            HTTPStatus.NOT_FOUND,
            {"message": f"mock route not found for {method} {parsed.path}"},
        )

    def _load_fixture_routes(self) -> tuple[dict[RouteKey, dict[str, object]], dict[str, str]]:
        routes: dict[RouteKey, dict[str, object]] = {}
        fixture_names: dict[str, str] = {}
        for path in sorted(self.fixture_dir.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                continue
            typed_document = cast(dict[str, object], document)
            name = typed_document.get("name")
            request_path = typed_document.get("request_path")
            request_params = typed_document.get("request_params")
            response = typed_document.get("response")
            if (
                not isinstance(name, str)
                or not isinstance(request_path, str)
                or not isinstance(response, dict)
            ):
                continue
            if request_params is None:
                request_params = {}
            if not isinstance(request_params, dict):
                continue
            route_key = (
                request_path,
                self._mapping_query(cast(Mapping[object, object], request_params)),
            )
            routes[route_key] = cast(dict[str, object], response)
            fixture_names[request_path] = name
        return routes, fixture_names

    def _schema_list(self, prefix: str, collection_path: str) -> dict[str, object]:
        schemas = [
            response
            for (path, _query), response in sorted(self._routes.items())
            if prefix in self._fixture_names.get(path, "")
        ]
        return {
            "type": "collection",
            "data": schemas,
            "links": {"self": f"https://rancher.example.test{collection_path}"},
        }

    def _login_response(self, query: QueryKey, body: bytes) -> MockResponse:
        if dict(query).get("action") != "login":
            return self._json_response(HTTPStatus.NOT_FOUND, {"message": "unknown login action"})
        payload = self._decode_json(body)
        if payload.get("username") != self.username or payload.get("password") != self.password:
            return self._json_response(HTTPStatus.UNAUTHORIZED, {"message": "invalid credentials"})
        return self._json_response(HTTPStatus.OK, {"token": self.token, "type": "token"})

    def _decode_json(self, body: bytes) -> dict[str, object]:
        if not body.strip():
            return {}
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("mock server expected a JSON object request body")
        return cast(dict[str, object], payload)

    def _norman_root(self) -> dict[str, object]:
        return {
            "type": "apiRoot",
            "apiVersion": "v3",
            "links": {
                "schemas": "https://rancher.example.test/v3/schemas",
                "clusters": "https://rancher.example.test/v3/clusters",
                "settings": "https://rancher.example.test/v3/settings",
            },
        }

    def _steve_root(self, root_path: str) -> dict[str, object]:
        return {
            "type": "apiRoot",
            "apiVersion": "v1",
            "links": {
                "schemas": f"https://rancher.example.test{root_path}/schemas",
                "namespaces": f"https://rancher.example.test{root_path}/namespaces",
                "services": f"https://rancher.example.test{root_path}/services",
            },
        }

    def _mapping_query(self, params: Mapping[object, object]) -> QueryKey:
        return tuple(sorted((str(key), str(value)) for key, value in params.items()))

    def _normalize_query(self, query: str) -> QueryKey:
        return tuple(sorted(parse_qsl(query, keep_blank_values=True)))

    def _json_response(self, status_code: int, payload: Mapping[str, object]) -> MockResponse:
        return MockResponse(
            status_code=status_code,
            content_type="application/json; charset=utf-8",
            body=(json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"),
        )


def _handler_class(state: MockRancherState) -> type[BaseHTTPRequestHandler]:
    class MockRancherHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self._write_response(state.handle("GET", self.path, dict(self.headers.items()), b""))

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b""
            self._write_response(state.handle("POST", self.path, dict(self.headers.items()), body))

        def log_message(self, format: str, *args: object) -> None:
            return

        def _write_response(self, response: MockResponse) -> None:
            self.send_response(response.status_code)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

    return MockRancherHandler


def build_parser() -> argparse.ArgumentParser:
    """Build the mock-server CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=18443, type=int)
    parser.add_argument("--fixture-dir", default=str(DEFAULT_FIXTURE_DIR))
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--cluster-id", default=DEFAULT_CLUSTER_ID)
    parser.add_argument("--rancher-version", default=DEFAULT_VERSION)
    return parser


def main() -> None:
    """Run the fixture-backed mock Rancher server."""

    args = build_parser().parse_args()
    state = MockRancherState(
        fixture_dir=Path(args.fixture_dir),
        username=args.username,
        password=args.password,
        token=args.token,
        cluster_id=args.cluster_id,
        rancher_version=args.rancher_version,
    )
    server = ThreadingHTTPServer((args.host, args.port), _handler_class(state))
    print(f"mock rancher listening on http://{args.host}:{args.port} (user={args.username})")  # noqa: T201
    server.serve_forever()


if __name__ == "__main__":
    main()
