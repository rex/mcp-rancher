"""Tool-call metrics emitted as structured log lines.

The MCP server runs over stdio in production, so a Prometheus
``/metrics`` HTTP endpoint would require a side-channel HTTP server
that interferes with the stdio transport. Instead, every tool call
emits one structured ``MetricEntry`` to the dedicated
``rancher_mcp.metrics`` logger. Downstream log aggregation
(Promtail → Loki + recording rules, Vector + Prometheus, fluentd +
file-based exporter, etc.) derives the histograms and counters from
these records.

Apply with ``apply_metrics_to_all_tools(mcp)`` at FastMCP
construction time; this is the inner wrapper, ``wrap_with_structured_errors``
is the outer wrapper, so metrics see the original ``RancherMCPError``
with its real ``error_code`` before that exception gets translated to
``ToolError`` at the MCP boundary.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any, Literal

import structlog
from pydantic import BaseModel, ConfigDict

from rancher_mcp.exceptions import RancherMCPError

MetricOutcome = Literal["success", "error"]
"""Whether the tool call returned normally or raised RancherMCPError."""


class MetricEntry(BaseModel):
    """One structured metric record per tool call."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    outcome: MetricOutcome
    duration_ms: int
    error_code: str | None = None


_metrics_logger = structlog.get_logger("rancher_mcp.metrics")


def emit_metric(entry: MetricEntry) -> None:
    """Emit one metric record to the dedicated metrics logger."""

    _metrics_logger.info(
        "metric",
        **entry.model_dump(exclude_none=True),
    )


def track_metric(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Wrap an async tool function to emit one metric record per call.

    Captures wall-clock duration in milliseconds. On success emits
    ``outcome=success``; on ``RancherMCPError`` emits ``outcome=error``
    plus ``error_code`` and re-raises. Other exception types pass
    through unmetered (those are unexpected programming errors that
    should bubble up immediately to the MCP boundary).
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = monotonic()
        try:
            result = await fn(*args, **kwargs)
        except RancherMCPError as exc:
            emit_metric(
                MetricEntry(
                    tool_name=fn.__name__,
                    outcome="error",
                    duration_ms=int((monotonic() - start) * 1000),
                    error_code=exc.error_code,
                )
            )
            raise
        emit_metric(
            MetricEntry(
                tool_name=fn.__name__,
                outcome="success",
                duration_ms=int((monotonic() - start) * 1000),
            )
        )
        return result

    return wrapper


def apply_metrics_to_all_tools(mcp: Any) -> None:
    """Wrap every registered tool's fn with ``track_metric``.

    Call once at server construction time, BEFORE
    ``apply_structured_errors_to_all_tools`` so the structured-error
    translation is the OUTER layer and metrics see the original
    ``RancherMCPError`` before it becomes a ``ToolError``.
    """

    for tool in mcp._tool_manager._tools.values():
        tool.fn = track_metric(tool.fn)
