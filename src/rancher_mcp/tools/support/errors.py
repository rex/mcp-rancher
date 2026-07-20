"""Structured error handling for MCP tool responses."""

from __future__ import annotations

import functools
import json
from collections.abc import Callable
from typing import Any

import structlog
from mcp.server.fastmcp.exceptions import ToolError

from rancher_mcp.exceptions import RancherAPIError, RancherMCPError

_logger = structlog.get_logger("rancher_mcp.tools.errors")


def _error_envelope(exc: Exception) -> str:
    payload: dict[str, Any] = {
        "error_code": getattr(exc, "error_code", "MCP_ERROR"),
        # Never emit an empty message: an httpx timeout stringifies to "",
        # which is exactly the opaque "Error executing tool X:" (nothing after
        # the colon) the operator hit when the Rancher tunnel dropped. K-5.
        "message": str(exc) or type(exc).__name__,
    }
    hint = getattr(exc, "hint", None)
    if hint:
        payload["hint"] = hint
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
        except ToolError:
            raise
        except Exception as exc:
            # Backstop: an unforeseen exception (or one whose str() is empty)
            # must never reach FastMCP as a bare "Error executing tool X:"
            # with nothing after the colon. Log it and surface a structured,
            # guaranteed-non-empty envelope. K-5.
            _logger.error(
                "tool_unexpected_error",
                tool=getattr(fn, "__name__", "unknown"),
                exc_info=True,
            )
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
