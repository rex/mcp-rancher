"""Structured-error boundary tests (Track A-2 regression guard)."""

from __future__ import annotations

import json

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from rancher_mcp.exceptions import (
    RancherCapabilityError,
    RancherManagementPlaneUnreachableError,
    RancherNotFoundError,
)
from rancher_mcp.tools.support.errors import wrap_with_structured_errors


async def test_capability_error_wraps_to_structured_tool_error() -> None:
    """A read-only-instance rejection surfaces as a structured ToolError envelope.

    Regression guard for Track A-2: the write-safety guards raise
    RancherCapabilityError; the boundary must translate that into a JSON
    envelope the agent can branch on via error_code, never a raw string that
    trips Pydantic output-model validation.
    """

    async def _guarded() -> str:
        raise RancherCapabilityError("instance 'prod' is configured read-only for mutations")

    wrapped = wrap_with_structured_errors(_guarded)
    with pytest.raises(ToolError) as excinfo:
        await wrapped()

    envelope = json.loads(str(excinfo.value))
    assert envelope["error_code"] == "CAPABILITY_ERROR"
    assert "read-only" in envelope["message"]
    assert "http_status" not in envelope


async def test_api_error_envelope_includes_http_status_and_field() -> None:
    """API errors carry error_code, http_status, and field in the envelope."""

    async def _guarded() -> str:
        raise RancherNotFoundError(404, "namespace not found", field="metadata.name")

    wrapped = wrap_with_structured_errors(_guarded)
    with pytest.raises(ToolError) as excinfo:
        await wrapped()

    envelope = json.loads(str(excinfo.value))
    assert envelope["error_code"] == "NOT_FOUND"
    assert envelope["http_status"] == 404
    assert envelope["field"] == "metadata.name"


async def test_successful_call_passes_through_untouched() -> None:
    """Non-error returns are returned verbatim."""

    async def _ok() -> str:
        return "ok"

    assert await wrap_with_structured_errors(_ok)() == "ok"


async def test_empty_message_never_produces_blank_envelope() -> None:
    """An exception whose str() is empty must not yield a blank message (K-5).

    This is the exact failure the operator hit: an httpx timeout stringifies
    to "", producing "Error executing tool X:" with nothing after the colon.
    """

    async def _boom() -> str:
        raise RuntimeError("")

    with pytest.raises(ToolError) as excinfo:
        await wrap_with_structured_errors(_boom)()

    envelope = json.loads(str(excinfo.value))
    assert envelope["message"] == "RuntimeError"  # falls back to the type name
    assert envelope["error_code"] == "MCP_ERROR"


async def test_unexpected_exception_is_backstopped_as_structured_error() -> None:
    """A non-RancherMCPError is caught and surfaced as a structured envelope (K-5)."""

    async def _boom() -> str:
        raise ValueError("kaboom")

    with pytest.raises(ToolError) as excinfo:
        await wrap_with_structured_errors(_boom)()

    envelope = json.loads(str(excinfo.value))
    assert envelope["error_code"] == "MCP_ERROR"
    assert envelope["message"] == "kaboom"


async def test_management_plane_unreachable_envelope_carries_code_and_hint() -> None:
    """The tunnel-down error surfaces its code and node-local hint (K-5)."""

    async def _boom() -> str:
        raise RancherManagementPlaneUnreachableError("tunnel down for GET /v3/pods")

    with pytest.raises(ToolError) as excinfo:
        await wrap_with_structured_errors(_boom)()

    envelope = json.loads(str(excinfo.value))
    assert envelope["error_code"] == "MANAGEMENT_PLANE_UNREACHABLE"
    assert "node-local" in envelope["hint"]
    assert envelope["message"]
