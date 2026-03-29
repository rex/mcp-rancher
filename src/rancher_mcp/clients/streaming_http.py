"""HTTP streaming helpers for the Rancher streaming client."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import cast

import httpx

from rancher_mcp.clients.streaming_transport import raise_for_status
from rancher_mcp.exceptions import RancherAPIError
from rancher_mcp.models.streaming import JSONEventStreamCapture, TextLineStreamCapture


async def stream_text_lines(
    *,
    client: httpx.AsyncClient,
    instance_name: str,
    path: str,
    params: tuple[tuple[str, str], ...],
    max_lines: int,
    idle_timeout_seconds: float,
) -> TextLineStreamCapture:
    """Read a bounded text-line stream from a Rancher endpoint."""

    lines: list[str] = []
    truncated = False

    async with client.stream("GET", path, params=params) as response:
        raise_for_status(response)
        iterator = response.aiter_lines()
        while len(lines) < max_lines:
            line = await next_with_timeout(iterator, idle_timeout_seconds)
            if line is None:
                break
            if not line:
                continue
            lines.append(line)
        else:
            truncated = True

    return TextLineStreamCapture(
        instance=instance_name,
        path=path,
        line_count=len(lines),
        truncated=truncated,
        lines=lines,
    )


async def stream_json_lines(
    *,
    client: httpx.AsyncClient,
    instance_name: str,
    path: str,
    params: tuple[tuple[str, str], ...],
    max_events: int,
    idle_timeout_seconds: float,
) -> JSONEventStreamCapture:
    """Read a bounded JSON-line stream from a Rancher endpoint."""

    events: list[dict[str, object]] = []
    truncated = False

    async with client.stream("GET", path, params=params) as response:
        raise_for_status(response)
        iterator = response.aiter_lines()
        while len(events) < max_events:
            line = await next_with_timeout(iterator, idle_timeout_seconds)
            if line is None:
                break
            if not line:
                continue
            payload: object = json.loads(line)
            if not isinstance(payload, dict):
                raise RancherAPIError(
                    response.status_code,
                    "Expected each streamed watch event to be a JSON object",
                )
            events.append(cast(dict[str, object], payload))
        else:
            truncated = True

    return JSONEventStreamCapture(
        instance=instance_name,
        path=path,
        event_count=len(events),
        truncated=truncated,
        events=events,
    )


async def next_with_timeout(
    iterator: AsyncIterator[str],
    idle_timeout_seconds: float,
) -> str | None:
    """Read the next async text line with an idle timeout."""

    try:
        return await asyncio.wait_for(
            iterator.__anext__(),
            timeout=idle_timeout_seconds,
        )
    except TimeoutError:
        return None
    except StopAsyncIteration:
        return None
