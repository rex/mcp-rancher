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
