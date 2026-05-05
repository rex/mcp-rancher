"""Structured error handling for MCP tool responses."""

from __future__ import annotations

import functools
import json
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp.exceptions import ToolError

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
    """Wrap an async tool function so RancherMCPError surfaces a structured envelope.

    Raises ``ToolError`` carrying a JSON envelope with ``error_code``,
    ``message``, and (for API errors) ``http_status``/``field``. FastMCP
    converts ``ToolError`` to a ``CallToolResult`` with ``isError=True`` and
    ``TextContent`` containing the envelope verbatim. The agent parses the
    text to dispatch on ``error_code``.

    Without this wrapper, the boundary trips on ``ValidationError`` because
    a plain string return cannot be coerced into a typed Pydantic return
    model (e.g. ``GenericResourceMutationResult``). Raising ``ToolError``
    bypasses outputSchema validation entirely and uses the MCP-native
    error path instead.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except RancherMCPError as exc:
            raise ToolError(_error_envelope(exc)) from exc

    return wrapper


def apply_structured_errors_to_all_tools(mcp: Any) -> None:
    """Patch every registered tool's fn to return structured errors on failure.

    Called once after all tools are registered in create_mcp_server().
    Uses FastMCP's internal _tool_manager._tools dict — call only at server
    construction time, never at request time.
    """
    for tool in mcp._tool_manager._tools.values():
        tool.fn = wrap_with_structured_errors(tool.fn)
