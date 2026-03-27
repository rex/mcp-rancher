"""Capture and sanitize live Rancher contract fixtures for tests."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

LAB_HOSTNAMES = (
    "127.0.0.1.sslip.io",
    "127.0.0.1",
)
LAB_BASE_URLS = tuple(f"https://{hostname}:8443" for hostname in LAB_HOSTNAMES)
LAB_WS_BASE_URLS = tuple(f"wss://{hostname}:8443" for hostname in LAB_HOSTNAMES)
SANITIZED_BASE_URL = "https://rancher.example.test"
SANITIZED_WS_BASE_URL = "wss://rancher.example.test"
RAW_FIXTURE_DIR = Path(".lab/contract-fixtures/raw")
DEFAULT_OUTPUT_DIR = Path("tests/fixtures/rancher_2_6_5")

QueryParams = Mapping[str, str | int | bool]
FetchJson = Callable[[str, QueryParams | None], dict[str, object]]

_VOLATILE_VALUE_KEYS = frozenset(
    {
        "uid",
        "resourceVersion",
        "creationTimestamp",
        "deletionTimestamp",
        "managedFields",
        "continue",
        "created",
        "createdTS",
        "uuid",
    }
)
_VOLATILE_METADATA_KEYS = frozenset(
    {
        "uid",
        "resourceVersion",
        "creationTimestamp",
        "deletionTimestamp",
        "managedFields",
        "generation",
        "fields",
        "relationships",
    }
)
_VOLATILE_ANNOTATION_KEYS = frozenset(
    {
        "cattle.io/status",
        "control-plane.alpha.kubernetes.io/leader",
        "deployment.kubernetes.io/revision",
        "kubectl.kubernetes.io/last-applied-configuration",
    }
)
_UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_TIMESTAMP_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\b")
_PROJECT_ID_PATTERN = re.compile(r"\bp-[a-z0-9]{4,}\b")


def _empty_query_params() -> dict[str, str | int | bool]:
    """Return a typed empty query-param mapping."""

    return {}


@dataclass(frozen=True)
class FixtureSpec:
    """Declarative live-fixture request."""

    name: str
    path: str
    params: dict[str, str | int | bool] = field(default_factory=_empty_query_params)


def default_fixture_specs() -> tuple[FixtureSpec, ...]:
    """Return the canonical Rancher 2.6.5 contract-fixture capture set."""

    return (
        FixtureSpec(
            name="norman_schema_cluster",
            path="/v3/schemas/cluster",
        ),
        FixtureSpec(
            name="norman_collection_clusters",
            path="/v3/clusters",
            params={"limit": 2},
        ),
        FixtureSpec(
            name="norman_resource_cluster_local",
            path="/v3/clusters/local",
        ),
        FixtureSpec(
            name="norman_collection_settings_filtered",
            path="/v3/settings",
            params={"limit": 2, "sort": "name", "source": "default"},
        ),
        FixtureSpec(
            name="steve_schema_namespace",
            path="/k8s/clusters/venue-local/v1/schemas/namespace",
        ),
        FixtureSpec(
            name="steve_schema_service",
            path="/k8s/clusters/venue-local/v1/schemas/service",
        ),
        FixtureSpec(
            name="steve_collection_namespaces",
            path="/k8s/clusters/venue-local/v1/namespaces",
            params={"limit": 2},
        ),
        FixtureSpec(
            name="steve_resource_namespace_cattle_system",
            path="/k8s/clusters/venue-local/v1/namespaces/cattle-system",
        ),
        FixtureSpec(
            name="steve_collection_services",
            path="/k8s/clusters/venue-local/v1/services",
            params={"limit": 2},
        ),
        FixtureSpec(
            name="steve_resource_service_default_kubernetes",
            path="/k8s/clusters/venue-local/v1/services/default/kubernetes",
        ),
    )


def login_to_rancher(
    *,
    base_url: str,
    username: str,
    password: str,
) -> str:
    """Authenticate against a Rancher instance and return a bearer token."""

    response = httpx.post(
        f"{base_url}/v3-public/localProviders/local?action=login",
        json={"username": username, "password": password},
        verify=False,  # noqa: S501
        timeout=httpx.Timeout(30.0, connect=10.0),
    )
    response.raise_for_status()
    payload: object = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Rancher login did not return a JSON object")
    typed_payload = cast(dict[str, object], payload)
    token = typed_payload.get("token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Rancher login response did not include a bearer token")
    return token


def fetch_json_from_rancher(
    *,
    base_url: str,
    token: str,
    path: str,
    params: QueryParams | None = None,
) -> dict[str, object]:
    """Fetch one JSON object from Rancher."""

    with httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={"Authorization": f"Bearer {token}"},
        verify=False,  # noqa: S501
        timeout=httpx.Timeout(30.0, connect=10.0),
    ) as client:
        response = client.get(path, params=params)
        response.raise_for_status()
        payload: object = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"Fixture request {path} did not return a JSON object")
        return cast(dict[str, object], payload)


def capture_contract_fixtures(
    *,
    output_dir: Path,
    raw_output_dir: Path,
    fetch_json: FetchJson,
    fixture_specs: tuple[FixtureSpec, ...] | None = None,
) -> list[Path]:
    """Capture and sanitize the canonical contract fixtures into the repo."""

    specs = fixture_specs or default_fixture_specs()
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_output_dir.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []
    for spec in specs:
        raw_payload = fetch_json(spec.path, spec.params or None)
        raw_path = raw_output_dir / f"{spec.name}.json"
        raw_path.write_text(
            json.dumps(raw_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        sanitized_payload = sanitize_fixture_payload(raw_payload)
        document = {
            "name": spec.name,
            "request_path": spec.path,
            "request_params": dict(spec.params),
            "response": sanitized_payload,
        }
        output_path = output_dir / f"{spec.name}.json"
        output_path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written_paths.append(output_path)
    return written_paths


def sanitize_fixture_payload(payload: object) -> object:
    """Recursively sanitize live Rancher payloads into committed contract fixtures."""

    if isinstance(payload, dict):
        typed_payload = cast(dict[str, object], payload)
        return {
            key: sanitize_fixture_payload(_sanitize_mapping_value(key, value))
            for key, value in sorted(typed_payload.items())
            if _include_mapping_key(key, value)
        }
    if isinstance(payload, list):
        typed_payload = cast(list[object], payload)
        return [sanitize_fixture_payload(item) for item in typed_payload]
    if isinstance(payload, str):
        return _sanitize_string(payload)
    return payload


def _sanitize_mapping_value(key: str, value: object) -> object:
    """Normalize mapping values for unstable Rancher fields."""

    if key in _VOLATILE_VALUE_KEYS:
        if key == "continue":
            return "<continue-token>"
        return f"<sanitized:{key}>"

    if key == "metadata" and isinstance(value, dict):
        typed_value = cast(dict[str, object], value)
        return {
            child_key: child_value
            for child_key, child_value in typed_value.items()
            if child_key not in _VOLATILE_METADATA_KEYS
        }

    if key == "annotations" and isinstance(value, dict):
        typed_value = cast(dict[str, object], value)
        return {
            child_key: child_value
            for child_key, child_value in typed_value.items()
            if child_key not in _VOLATILE_ANNOTATION_KEYS
        }

    return value


def _include_mapping_key(key: str, value: object) -> bool:
    """Return whether a key should be included in the sanitized output."""

    if key == "managedFields":
        return False
    if key != "annotations" or not isinstance(value, dict):
        return True
    typed_value = cast(dict[object, object], value)
    return len(typed_value) > 0


def _sanitize_string(value: str) -> str:
    """Normalize URLs and opaque continuation markers in string values."""

    sanitized = value
    for base_url in LAB_BASE_URLS:
        sanitized = sanitized.replace(base_url, SANITIZED_BASE_URL)
    for base_url in LAB_WS_BASE_URLS:
        sanitized = sanitized.replace(base_url, SANITIZED_WS_BASE_URL)
    sanitized = sanitized.replace("127.0.0.1.sslip.io", "rancher.example.test")
    sanitized = sanitized.replace("sslip.io", "example.test")
    sanitized = _UUID_PATTERN.sub("<sanitized:uuid>", sanitized)
    sanitized = _TIMESTAMP_PATTERN.sub("<sanitized:timestamp>", sanitized)
    sanitized = _PROJECT_ID_PATTERN.sub("p-sanitized", sanitized)

    if sanitized.startswith(("https://", "wss://")):
        return _sanitize_url(sanitized)
    return sanitized


def _sanitize_url(value: str) -> str:
    """Normalize Rancher URLs in fixture payloads."""

    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return value

    query_pairs: list[tuple[str, str]] = []
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        if key == "continue":
            query_pairs.append((key, "<continue-token>"))
            continue
        query_pairs.append((key, item))

    return urlunsplit(
        (
            parsed.scheme,
            "rancher.example.test",
            parsed.path,
            urlencode(query_pairs),
            parsed.fragment,
        )
    )


def committed_fixture_paths(output_dir: Path) -> list[Path]:
    """Return committed fixture JSON files in deterministic order."""

    return sorted(output_dir.glob("*.json"))


def fixture_contains_unsanitized_runtime_data(document: str) -> bool:
    """Return whether a fixture still contains obvious live-lab data."""

    return any(marker in document for marker in (*LAB_HOSTNAMES, "token-"))
