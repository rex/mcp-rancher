"""Structured error handling for MCP tool responses."""

from __future__ import annotations

import functools
import json
from collections.abc import Callable
from typing import Any

from rancher_mcp.exceptions import RancherAPIError, RancherMCPError


def _error_envelope(exc: RancherMCPError) -> str:
    payload: dict[str, Any] = {
        "error_code": exc.error_code,
        "message": str(exc),
    }
    if isinstance(exc, RancherAPIError):
        payload["http_status"] = exc.status_code
        if exc.field:
            payload["field"] = exc.field
    return json.dumps(payload)


def wrap_with_structured_errors(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap an async tool function so RancherMCPError becomes a structured JSON response."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except RancherMCPError as exc:
            return _error_envelope(exc)

    return wrapper


def apply_structured_errors_to_all_tools(mcp: Any) -> None:
    """Patch every registered tool's fn to return structured errors on failure.

    Called once after all tools are registered in create_mcp_server().
    Uses FastMCP's internal _tool_manager._tools dict — call only at server
    construction time, never at request time.
    """
    for tool in mcp._tool_manager._tools.values():
        tool.fn = wrap_with_structured_errors(tool.fn)
