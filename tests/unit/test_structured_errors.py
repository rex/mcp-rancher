"""Structured-error boundary tests (Track A-2 regression guard)."""

from __future__ import annotations

import json

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from rancher_mcp.exceptions import RancherCapabilityError, RancherNotFoundError
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
