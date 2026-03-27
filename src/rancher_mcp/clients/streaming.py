"""Rancher streaming and WebSocket client."""

from __future__ import annotations

import asyncio
import json
import ssl
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import cast
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed
from websockets.typing import Subprotocol

from rancher_mcp.exceptions import RancherAPIError
from rancher_mcp.models.discovery import RancherInstanceConfig
from rancher_mcp.models.streaming import (
    JSONEventStreamCapture,
    TextLineStreamCapture,
    WebSocketCapture,
    WebSocketFrame,
)

type StreamParamValue = str | int | bool
type StreamParams = Mapping[str, StreamParamValue] | Sequence[tuple[str, StreamParamValue]]
type WebSocketMessage = str | bytes

KUBERNETES_STREAM_SUBPROTOCOLS: tuple[Subprotocol, ...] = cast(
    tuple[Subprotocol, ...],
    (
        "v5.channel.k8s.io",
        "v4.channel.k8s.io",
        "v3.channel.k8s.io",
        "v2.channel.k8s.io",
        "channel.k8s.io",
        "base64.channel.k8s.io",
    ),
)

_KUBERNETES_CHANNEL_NAMES = {
    0: "stdin",
    1: "stdout",
    2: "stderr",
    3: "error",
    4: "resize",
    5: "status",
}


class RancherStreamingClient:
    """Async streaming client for Rancher HTTP stream and WebSocket endpoints."""

    def __init__(
        self,
        instance_name: str,
        config: RancherInstanceConfig,
        timeout: httpx.Timeout | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.instance_name = instance_name
        self._base_url = config.url.rstrip("/")
        self._token = config.token.get_secret_value()
        self._ssl = _ssl_context_from_config(config)
        verify: str | bool = config.ca_bundle or config.verify_ssl
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=timeout or httpx.Timeout(30.0, connect=10.0),
            verify=verify,
            transport=transport,
        )

    async def __aenter__(self) -> RancherStreamingClient:
        """Enter the async context manager."""

        return self

    async def __aexit__(self, *_args: object) -> None:
        """Close the underlying HTTP client on exit."""

        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""

        await self._client.aclose()

    async def stream_text_lines(
        self,
        path: str,
        *,
        params: StreamParams | None = None,
        max_lines: int = 100,
        idle_timeout_seconds: float = 2.0,
    ) -> TextLineStreamCapture:
        """Read a bounded text-line stream from a Rancher endpoint."""

        lines: list[str] = []
        truncated = False

        async with self._client.stream(
            "GET",
            path,
            params=_normalize_params(params),
        ) as response:
            _raise_for_status(response)
            iterator = response.aiter_lines()
            while len(lines) < max_lines:
                line = await _next_with_timeout(iterator, idle_timeout_seconds)
                if line is None:
                    break
                if not line:
                    continue
                lines.append(line)
            else:
                truncated = True

        return TextLineStreamCapture(
            instance=self.instance_name,
            path=path,
            line_count=len(lines),
            truncated=truncated,
            lines=lines,
        )

    async def stream_json_lines(
        self,
        path: str,
        *,
        params: StreamParams | None = None,
        max_events: int = 100,
        idle_timeout_seconds: float = 2.0,
    ) -> JSONEventStreamCapture:
        """Read a bounded JSON-line stream from a Rancher endpoint."""

        events: list[dict[str, object]] = []
        truncated = False

        async with self._client.stream(
            "GET",
            path,
            params=_normalize_params(params),
        ) as response:
            _raise_for_status(response)
            iterator = response.aiter_lines()
            while len(events) < max_events:
                line = await _next_with_timeout(iterator, idle_timeout_seconds)
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
            instance=self.instance_name,
            path=path,
            event_count=len(events),
            truncated=truncated,
            events=events,
        )

    async def websocket_capture(
        self,
        path: str,
        *,
        params: StreamParams | None = None,
        subprotocols: Sequence[Subprotocol] | None = None,
        outbound_messages: Sequence[WebSocketMessage] | None = None,
        max_messages: int = 20,
        idle_timeout_seconds: float = 2.0,
    ) -> WebSocketCapture:
        """Capture a bounded WebSocket exchange against a Rancher endpoint."""

        websocket_url = _websocket_url(self._base_url, path, params)
        frames: list[WebSocketFrame] = []
        truncated = False

        async with connect(
            websocket_url,
            additional_headers={"Authorization": f"Bearer {self._token}"},
            subprotocols=tuple(subprotocols) if subprotocols else None,
            open_timeout=10,
            close_timeout=2,
            ssl=self._ssl,
        ) as websocket:
            for message in outbound_messages or ():
                await websocket.send(message)

            while len(frames) < max_messages:
                try:
                    raw_message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=idle_timeout_seconds,
                    )
                except TimeoutError:
                    break
                except ConnectionClosed:
                    break

                frames.append(_frame_from_message(raw_message))
            else:
                truncated = True

            negotiated_subprotocol = websocket.subprotocol

        return WebSocketCapture(
            instance=self.instance_name,
            path=path,
            negotiated_subprotocol=negotiated_subprotocol,
            frame_count=len(frames),
            truncated=truncated,
            frames=frames,
        )


async def _next_with_timeout(
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


def _normalize_params(params: StreamParams | None) -> tuple[tuple[str, str], ...]:
    """Normalize scalar or repeated query params for HTTP and WebSocket requests."""

    if params is None:
        return ()

    if isinstance(params, Mapping):
        return tuple((key, _stringify_param(value)) for key, value in params.items())
    return tuple((key, _stringify_param(value)) for key, value in params)


def _stringify_param(value: StreamParamValue) -> str:
    """Stringify one query-param value for transport."""

    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _ssl_context_from_config(config: RancherInstanceConfig) -> ssl.SSLContext | None:
    """Build the SSL configuration needed for WebSocket connections."""

    parsed = urlsplit(config.url)
    if parsed.scheme != "https":
        return None

    if config.ca_bundle:
        return ssl.create_default_context(cafile=config.ca_bundle)
    if config.verify_ssl:
        return ssl.create_default_context()

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _websocket_url(
    base_url: str,
    path: str,
    params: StreamParams | None,
) -> str:
    """Build a WebSocket URL for a Rancher endpoint."""

    parsed = urlsplit(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    normalized_path = path if path.startswith("/") else f"/{path}"
    query = urlencode(_normalize_params(params), doseq=True)
    return urlunsplit((scheme, parsed.netloc, normalized_path, query, ""))


def _frame_from_message(message: WebSocketMessage) -> WebSocketFrame:
    """Normalize one raw WebSocket message into a structured frame."""

    if isinstance(message, str):
        return WebSocketFrame(
            opcode="text",
            byte_length=len(message.encode("utf-8")),
            text=message,
        )

    channel_id: int | None = None
    channel_name: str | None = None
    text: str | None = None
    byte_length = len(message)

    if message:
        channel_id = message[0]
        channel_name = _KUBERNETES_CHANNEL_NAMES.get(channel_id, f"channel-{channel_id}")
        payload = message[1:]
        if payload:
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError:
                text = None

    return WebSocketFrame(
        opcode="binary",
        byte_length=byte_length,
        channel_id=channel_id,
        channel_name=channel_name,
        text=text,
    )


def _raise_for_status(response: httpx.Response) -> None:
    """Raise a typed Rancher API error for unsuccessful HTTP stream setup."""

    if response.is_success:
        return
    message = response.text.strip() or "Rancher streaming request failed"
    raise RancherAPIError(response.status_code, message)
