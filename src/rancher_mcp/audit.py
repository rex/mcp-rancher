"""Structured audit-trail logging for write operations.

Every mutation tool emits a structured ``AuditEntry`` to a dedicated
``rancher_mcp.audit`` logger after either successful completion or a
``RancherMCPError`` rejection. Argument *names* are captured (so the
forensic record shows what kind of call was made) but argument *values*
are intentionally omitted to keep secrets out of the log stream.

The audit logger inherits the global structlog configuration (JSON in
production, console in dev) — request_id / trace_id bound via
``structlog.contextvars`` are automatically merged into every record.

Apply with ``@audit_mutation(operation="apply", plane="steve")`` on the
public mutation entry point.

Satisfies VIBE.yaml ``security.audit_logging: required``.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any, Literal

import structlog
from pydantic import BaseModel, ConfigDict, Field

from rancher_mcp.exceptions import RancherAPIError, RancherMCPError

AuditOutcome = Literal["success", "error"]
"""Whether the audited call returned normally or raised RancherMCPError."""


class AuditEntry(BaseModel):
    """One structured audit record emitted on every mutation tool call."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    operation: str
    plane: str
    outcome: AuditOutcome
    instance: str | None = None
    schema_id: str | None = None
    resource_id: str | None = None
    cluster_id: str | None = None
    namespace: str | None = None
    arg_keys: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    http_status: int | None = None


_audit_logger = structlog.get_logger("rancher_mcp.audit")


def emit_audit(entry: AuditEntry) -> None:
    """Emit one audit record to the dedicated audit logger.

    Uses ``log("audit", **fields)`` so the record carries the
    ``event="audit"`` key for grep/filter pipelines.
    """

    _audit_logger.info(
        "audit",
        **entry.model_dump(exclude_none=True),
    )


def _build_entry_kwargs(
    fn: Callable[..., Any],
    operation: str,
    plane: str,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Extract the entry fields shared between success and error paths."""

    return {
        "tool_name": fn.__name__,
        "operation": operation,
        "plane": plane,
        "instance": kwargs.get("instance"),
        "schema_id": kwargs.get("schema_id"),
        "resource_id": kwargs.get("resource_id"),
        "cluster_id": kwargs.get("cluster_id"),
        "namespace": kwargs.get("namespace"),
        "arg_keys": sorted(kwargs.keys()),
    }


def audit_mutation(
    *,
    operation: str,
    plane: str,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Decorator factory that wraps an async mutation tool with audit logging.

    Captures argument *names* (never values) plus a small set of
    well-known fields (``instance``, ``schema_id``, ``resource_id``,
    ``cluster_id``, ``namespace``) when present in kwargs. On success
    emits ``outcome=success``; on ``RancherMCPError`` emits
    ``outcome=error`` with ``error_code``, ``error_message``, and
    (for ``RancherAPIError``) ``http_status`` — then re-raises so
    upstream handlers continue to see the exception.

    The decorator is intentionally agnostic about positional args:
    only kwargs are inspected. MCP unpacks tool calls into kwargs,
    and tests in this repo also call mutation tools with kwargs.
    Positional invocations would still be audited, just without the
    arg-name detail.
    """

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            base = _build_entry_kwargs(fn, operation, plane, kwargs)
            try:
                result = await fn(*args, **kwargs)
            except RancherMCPError as exc:
                error_kwargs: dict[str, Any] = {
                    "outcome": "error",
                    "error_code": exc.error_code,
                    "error_message": str(exc),
                }
                if isinstance(exc, RancherAPIError):
                    error_kwargs["http_status"] = exc.status_code
                emit_audit(AuditEntry(**base, **error_kwargs))
                raise
            emit_audit(AuditEntry(**base, outcome="success"))
            return result

        return wrapper

    return decorator
