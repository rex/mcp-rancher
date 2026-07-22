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


# Read tools whose single-resource DETAIL intentionally reveals a real credential
# value (M-SEC). These are NOT covered by ``audit_mutation`` (they are reads), so
# each invocation must still leave a forensic ``operation="reveal"`` record —
# except that a *names-only* get is not a reveal at all (M-SEC-2).
# Keyed by REGISTERED tool name → (plane, the kwarg holding the resource id,
# the kwarg that gates whether THIS call actually revealed anything).
# A gate of ``None`` means the tool has no such gate and every successful call
# is unconditionally a reveal (``cluster_registration_token_get``'s whole
# purpose is the join command — unchanged by M-SEC-2, out of scope). A gate
# naming a kwarg (``secret_get``'s ``"reveal"``) means the record fires only
# when ``kwargs.get(gate_kwarg) is True`` — a plain names/counts get must not
# be logged as a credential reveal.
# Mutations that also return the detail (e.g. secret_create) are already audited
# via ``audit_mutation`` and are deliberately not re-listed here.
_REVEAL_TOOLS: dict[str, tuple[str, str, str | None]] = {
    "rancher_secret_get": ("steve", "secret_name", "reveal"),
    "rancher_cluster_registration_token_get": (
        "management",
        "cluster_registration_token_id",
        None,
    ),
}


def _wrap_reveal_audit(
    fn: Callable[..., Awaitable[Any]],
    tool_name: str,
    plane: str,
    id_kwarg: str,
    gate_kwarg: str | None = None,
) -> Callable[..., Awaitable[Any]]:
    """Wrap a reveal get tool to emit an audit record on each successful reveal.

    When ``gate_kwarg`` is set, the record fires only when the call's kwargs
    have that key set to ``True`` — e.g. ``secret_get``'s ``reveal`` (M-SEC-2):
    the default names/counts-only get is not a credential reveal and must not
    be logged as one. When ``gate_kwarg`` is ``None`` (default), every
    successful call is audited unconditionally — the original M-SEC behavior,
    preserved for tools with no reveal-gating parameter of their own.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await fn(*args, **kwargs)
        if gate_kwarg is not None and kwargs.get(gate_kwarg) is not True:
            return result
        emit_audit(
            AuditEntry(
                tool_name=tool_name,
                operation="reveal",
                plane=plane,
                outcome="success",
                instance=kwargs.get("instance"),
                cluster_id=kwargs.get("cluster_id"),
                namespace=kwargs.get("namespace"),
                resource_id=kwargs.get(id_kwarg),
                arg_keys=sorted(kwargs.keys()),
            )
        )
        return result

    return wrapper


def apply_sensitive_reveal_audit(mcp: Any) -> None:
    """Wrap each sensitive-reveal get tool so every credential reveal is audited.

    The single-resource get of a Secret / registration token can return the
    real value (M-SEC) — a legitimate, deliberate reveal that must nonetheless
    leave a forensic trail. Resource *identity* (instance/cluster/namespace/
    name) is captured; the value itself is never logged. A failed get reveals
    nothing, so no record is emitted on error. Since M-SEC-2, ``secret_get``'s
    reveal is opt-in (``reveal=True``); a plain names/counts get is gated out
    of the audit trail entirely (see ``_REVEAL_TOOLS``). Call once at server
    construction.
    """

    for tool in mcp._tool_manager._tools.values():
        info = _REVEAL_TOOLS.get(tool.name)
        if info is not None:
            plane, id_kwarg, gate_kwarg = info
            tool.fn = _wrap_reveal_audit(tool.fn, tool.name, plane, id_kwarg, gate_kwarg)
