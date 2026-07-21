"""Redact-don't-delete tests (ROADMAP L-0b / ADR-0002 rule #5).

K-1 removed the registration-token ``manifestUrl`` from the list entirely,
destroying the signal that a manifest exists. L-0b restores it as a marker (the
real join token never reaches the list) and exposes secret key *names* (never
values) so the consumer knows what a Secret contains.
"""

from __future__ import annotations

from rancher_mcp.models.fleet_registration import MANIFEST_URL_REDACTED
from rancher_mcp.tools.config_secrets.shared import secret_summary_from_payload
from rancher_mcp.tools.fleet_registration.shared import (
    cluster_registration_token_summary_from_payload,
)


def test_registration_list_signals_manifest_without_leaking_the_token() -> None:
    payload = {
        "id": "c-x:default-token",
        "name": "default-token",
        "state": "active",
        # The real manifest path embeds a bearer join token (SECRETJOINTOKEN).
        "manifestUrl": "https://x.example.com/i/SECRETJOINTOKEN.yaml",  # pragma: allowlist secret
    }
    dumped = cluster_registration_token_summary_from_payload(payload).model_dump(by_alias=True)
    assert dumped["manifestUrl"] == MANIFEST_URL_REDACTED  # a marker, not the token
    assert "SECRETJOINTOKEN" not in str(dumped)


def test_registration_list_omits_manifest_when_none_exists() -> None:
    dumped = cluster_registration_token_summary_from_payload(
        {"id": "c-x:t", "name": "t", "state": "active"}
    ).model_dump(by_alias=True)
    # None manifest_url → dropped by the L-0 envelope, not a misleading marker.
    assert "manifestUrl" not in dumped


def test_secret_list_exposes_key_names_never_values() -> None:
    payload = {
        "metadata": {"name": "tls-ingress", "namespace": "cattle-system"},
        "type": "kubernetes.io/tls",
        "data": {"tls.key": "QkFTRTY0S0VZ", "tls.crt": "QkFTRTY0Q1JU"},  # pragma: allowlist secret
    }
    dumped = secret_summary_from_payload(payload).model_dump(by_alias=True)
    assert dumped["dataKeys"] == ["tls.crt", "tls.key"]  # names, sorted
    assert dumped["dataKeyCount"] == 2
    assert "QkFTRTY0S0VZ" not in str(dumped)  # values never exposed
