"""Contract-fixture capture and sanitization tests."""

from __future__ import annotations

import json
from pathlib import Path

from devtools.contract_fixtures import (
    DEFAULT_OUTPUT_DIR,
    FixtureSpec,
    capture_contract_fixtures,
    committed_fixture_paths,
    default_fixture_specs,
    fixture_contains_unsanitized_runtime_data,
    sanitize_fixture_payload,
)


def test_sanitize_fixture_payload_normalizes_urls_and_volatile_fields() -> None:
    """Sanitization should keep structure while removing unstable runtime data."""

    sanitized = sanitize_fixture_payload(
        {
            "links": {
                "self": "https://127.0.0.1.sslip.io:8443/v3/clusters/local",
                "shell": "wss://127.0.0.1.sslip.io:8443/v3/clusters/local?shell=true",
                "next": (
                    "https://127.0.0.1.sslip.io:8443/k8s/clusters/venue-local/v1/pods"
                    "?continue=abc123&limit=2"
                ),
            },
            "pagination": {
                "continue": "abc123",
                "next": (
                    "https://127.0.0.1:8443/k8s/clusters/venue-local/v1/pods"
                    "?continue=abc123&limit=2"
                ),
            },
            "metadata": {
                "name": "cattle-system",
                "uid": "uid-123",
                "resourceVersion": "456",
                "creationTimestamp": "2026-01-01T00:00:00Z",
            },
            "annotations": {
                "cattle.io/status": (
                    '{"LastUpdateTime":"2026-03-27T18:15:45Z","Project":"p-kzmtj"}'
                ),
                "deployment.kubernetes.io/revision": "3",
                "safe": "keep-me",
            },
            "uuid": "45cab414-9bf7-4ef1-9972-3c85590e93a2",
        }
    )

    assert sanitized == {
        "annotations": {
            "safe": "keep-me",
        },
        "links": {
            "next": (
                "https://rancher.example.test/k8s/clusters/venue-local/v1/pods"
                "?continue=%3Ccontinue-token%3E&limit=2"
            ),
            "shell": "wss://rancher.example.test/v3/clusters/local?shell=true",
            "self": "https://rancher.example.test/v3/clusters/local",
        },
        "metadata": {
            "name": "cattle-system",
        },
        "pagination": {
            "continue": "<continue-token>",
            "next": (
                "https://rancher.example.test/k8s/clusters/venue-local/v1/pods"
                "?continue=%3Ccontinue-token%3E&limit=2"
            ),
        },
        "uuid": "<sanitized:uuid>",
    }


def test_capture_contract_fixtures_writes_raw_and_sanitized_documents(tmp_path: Path) -> None:
    """Fixture capture should persist both repo-local raw data and committed sanitized envelopes."""

    output_dir = tmp_path / "sanitized"
    raw_dir = tmp_path / "raw"

    fixtures = (FixtureSpec(name="example_norman", path="/v3/example", params={"limit": 1}),)

    captured = capture_contract_fixtures(
        output_dir=output_dir,
        raw_output_dir=raw_dir,
        fetch_json=lambda _path, _params: {
            "links": {"self": "https://127.0.0.1.sslip.io:8443/v3/example"},
            "metadata": {"name": "example", "uid": "uid-123"},
        },
        fixture_specs=fixtures,
    )

    assert captured == [output_dir / "example_norman.json"]
    raw_payload = json.loads((raw_dir / "example_norman.json").read_text(encoding="utf-8"))
    sanitized_payload = json.loads((output_dir / "example_norman.json").read_text(encoding="utf-8"))

    assert raw_payload["metadata"]["uid"] == "uid-123"
    assert sanitized_payload["request_path"] == "/v3/example"
    assert sanitized_payload["request_params"] == {"limit": 1}
    assert (
        sanitized_payload["response"]["links"]["self"] == "https://rancher.example.test/v3/example"
    )
    assert "uid" not in sanitized_payload["response"]["metadata"]


def test_committed_contract_fixtures_are_present_and_sanitized() -> None:
    """Committed contract fixtures should match the capture manifest and avoid live runtime data."""

    fixture_paths = committed_fixture_paths(DEFAULT_OUTPUT_DIR)

    assert len(fixture_paths) == len(default_fixture_specs())
    assert fixture_paths

    for path in fixture_paths:
        document = path.read_text(encoding="utf-8")
        parsed = json.loads(document)
        assert isinstance(parsed, dict)
        assert not fixture_contains_unsanitized_runtime_data(document)
