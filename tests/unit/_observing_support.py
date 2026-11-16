"""One client session and one intercepted network, for many observed calls.

``observe_call`` opens a session and a network interception for a single call —
right for a test about one tool. A gate that asks a question of every argument
of every tool makes thousands of calls, and spends nearly all its time on that
setup. ``observing`` keeps both open and hands back a function that observes
one call at a time, with the same ``Observation`` as its result.

The network, the audit log and the questions are cleared before each call, so
what a call's ``Observation`` holds is that call's alone.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import anyio
import httpx
import respx
from _write_guards_support import (
    _CALL_DEADLINE_SECONDS,  # pyright: ignore[reportPrivateUsage]
    _PLAUSIBLE_PAYLOAD,  # pyright: ignore[reportPrivateUsage]
    Observation,
    innermost_message,
    observation_of,
)
from mcp import Client
from mcp.server.mcpserver import MCPServer
from structlog.testing import capture_logs

ObservedCall = Callable[[str, dict[str, object]], Awaitable[Observation]]


@asynccontextmanager
async def observing(mcp: MCPServer, *, mode: str = "2026-07-28") -> AsyncIterator[ObservedCall]:
    """Yield a function that calls a tool on *mcp* and reports what it did.

    The client declares no elicitation, like most clients: nobody can be
    asked, so a destructive tool is held back by its own guards alone.
    """

    with respx.mock(assert_all_called=False) as router, capture_logs() as logs:
        router.route().mock(return_value=httpx.Response(200, json=_PLAUSIBLE_PAYLOAD))
        async with Client(mcp, mode=mode) as client:

            async def call(tool_name: str, arguments: dict[str, object]) -> Observation:
                router.calls.clear()
                logs.clear()
                result = None
                rejected_by_client: str | None = None
                try:
                    with anyio.fail_after(_CALL_DEADLINE_SECONDS):
                        result = await client.call_tool(tool_name, arguments)
                except TimeoutError as exc:
                    raise AssertionError(
                        f"{tool_name} did not return within {_CALL_DEADLINE_SECONDS:g}s"
                    ) from exc
                except Exception as exc:
                    # The client refused the result (it did not match the
                    # tool's outputSchema). The tool still ran; what it sent
                    # is on record.
                    rejected_by_client = innermost_message(exc)
                sent = [made.request for made in router.calls]
                return observation_of(result, sent, logs, rejected_by_client, [])

            yield call
