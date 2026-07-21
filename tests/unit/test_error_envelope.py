"""Error-envelope classification tests (ROADMAP L-3e / ADR-0002).

Every error carries a ``retryable`` branch — transient (retry) vs permanent
(stop) — plus a machine-branchable ``reason`` distinguishing a missing app from
a dropped tunnel, so the agent needn't parse English.
"""

from __future__ import annotations

import json

from rancher_mcp.exceptions import (
    RancherAPIError,
    RancherCapabilityError,
    RancherManagementPlaneUnreachableError,
    RancherNotFoundError,
)
from rancher_mcp.tools.support.errors import _error_envelope


def _env(exc: Exception) -> dict[str, object]:
    return json.loads(_error_envelope(exc))


def test_transient_errors_are_retryable() -> None:
    tunnel = _env(RancherManagementPlaneUnreachableError("tunnel down"))
    assert tunnel["retryable"] is True
    assert tunnel["reason"] == "tunnel_unavailable"


def test_permanent_errors_are_not_retryable() -> None:
    assert _env(RancherNotFoundError(404, "nope"))["retryable"] is False
    # A missing app is structurally distinct from a dropped tunnel.
    capability = _env(RancherCapabilityError("cis app not installed"))
    assert capability["retryable"] is False
    assert capability["reason"] == "not_installed"


def test_server_errors_retry_but_client_errors_do_not() -> None:
    assert _env(RancherAPIError(503, "unavailable"))["retryable"] is True
    assert _env(RancherAPIError(400, "bad request"))["retryable"] is False


def test_capability_unavailable_envelope_carries_structured_context() -> None:
    """M-A11/K-8b: the same envelope, extended with capability/resource/
    remediation/cluster — not a parallel shape.

    Curated tools whose app/CRD is an optional install attach this context
    when raising RancherCapabilityError; the envelope surfaces it alongside
    the existing reason/retryable classification from L-3e/K-8a.
    """

    exc = RancherCapabilityError(
        "The rancher-cis-benchmark app is not installed on this cluster.",
        capability="rancher-cis-benchmark",
        resource="cisscans",
        remediation=(
            "Install the rancher-cis-benchmark app via Apps & Marketplace, or skip CIS scanning."
        ),
        cluster_id="c-abc123",
    )
    envelope = _env(exc)
    assert envelope["error_code"] == "CAPABILITY_ERROR"
    assert envelope["reason"] == "not_installed"
    assert envelope["retryable"] is False
    assert envelope["capability"] == "rancher-cis-benchmark"
    assert envelope["resource"] == "cisscans"
    assert envelope["cluster"] == "c-abc123"
    assert "Apps & Marketplace" in envelope["remediation"]


def test_capability_error_without_structured_context_omits_new_fields() -> None:
    """Old raise sites (no capability/resource/...) must not gain empty keys."""

    envelope = _env(RancherCapabilityError("instance 'prod' is configured read-only for mutations"))
    assert "capability" not in envelope
    assert "resource" not in envelope
    assert "cluster" not in envelope
    assert "remediation" not in envelope
