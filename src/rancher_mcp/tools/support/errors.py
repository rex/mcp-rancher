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

# Error codes whose condition is transient — the agent should retry rather than
# give up. Everything else (NOT_FOUND, UNAUTHORIZED, CONFLICT, CAPABILITY_ERROR,
# CONFIGURATION_ERROR) is permanent for this call. L-3e / ADR-0002.
_RETRYABLE_CODES = frozenset({"MANAGEMENT_PLANE_UNREACHABLE", "RATE_LIMITED"})

# A coarse machine-branchable reason, so the agent needn't parse English. A
# missing app ("not_installed") is structurally distinct from a dropped tunnel
# ("tunnel_unavailable") even though both once surfaced as a bare 404/error.
_REASON_BY_CODE = {
    "MANAGEMENT_PLANE_UNREACHABLE": "tunnel_unavailable",
    "CAPABILITY_ERROR": "not_installed",
    "RATE_LIMITED": "rate_limited",
}


def _is_retryable(exc: Exception, code: str) -> bool:
    """True when the failure is transient (retry) vs permanent (stop). L-3e."""

    if code in _RETRYABLE_CODES:
        return True
    status = getattr(exc, "status_code", None)
    return isinstance(status, int) and status >= 500


def _error_envelope(exc: Exception) -> str:
    code = getattr(exc, "error_code", "MCP_ERROR")
    payload: dict[str, Any] = {
        "error_code": code,
        # Never emit an empty message: an httpx timeout stringifies to "",
        # which is exactly the opaque "Error executing tool X:" (nothing after
        # the colon) the operator hit when the Rancher tunnel dropped. K-5.
        "message": str(exc) or type(exc).__name__,
        # The field that matters most (L-3e): tells the agent to stop burning
        # calls vs retry, without parsing the message.
        "retryable": _is_retryable(exc, code),
    }
    reason = _REASON_BY_CODE.get(code)
    if reason:
        payload["reason"] = reason
    hint = getattr(exc, "hint", None)
    if hint:
        payload["hint"] = hint
    # M-A11/K-8b: capability-unavailable enrichment — same envelope, extended
    # (not a parallel one). getattr (not isinstance) mirrors the `hint`
    # pattern above: any exception carrying these attributes gets them
    # surfaced, not just RancherCapabilityError.
    capability = getattr(exc, "capability", None)
    if capability:
        payload["capability"] = capability
    resource = getattr(exc, "resource", None)
    if resource:
        payload["resource"] = resource
    cluster_id = getattr(exc, "cluster_id", None)
    if cluster_id:
        payload["cluster"] = cluster_id
    remediation = getattr(exc, "remediation", None)
    if remediation:
        payload["remediation"] = remediation
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
