"""Rancher streaming and WebSocket client."""

from __future__ import annotations

from collections.abc import Sequence

import httpx
from websockets.typing import Subprotocol

from rancher_mcp.clients.request_guard import refuse_unsafe_request
from rancher_mcp.clients.streaming_http import (
    stream_json_lines as _stream_json_lines,
)
from rancher_mcp.clients.streaming_http import (
    stream_text_lines as _stream_text_lines,
)
from rancher_mcp.clients.streaming_transport import (
    StreamParams,
    normalize_params,
    ssl_context_from_config,
)
from rancher_mcp.clients.streaming_websocket import (
    KUBERNETES_STREAM_SUBPROTOCOLS as _KUBERNETES_STREAM_SUBPROTOCOLS,
)
from rancher_mcp.clients.streaming_websocket import (
    WebSocketMessage,
)
from rancher_mcp.clients.streaming_websocket import (
    websocket_capture as _websocket_capture,
)
from rancher_mcp.models.discovery import RancherInstanceConfig
from rancher_mcp.models.streaming import (
    JSONEventStreamCapture,
    TextLineStreamCapture,
    WebSocketCapture,
)

KUBERNETES_STREAM_SUBPROTOCOLS = _KUBERNETES_STREAM_SUBPROTOCOLS

# Kubernetes subresources that do something the moment a connection opens.
_SESSION_SUBRESOURCES = ("/exec", "/attach", "/portforward")

__all__ = ["KUBERNETES_STREAM_SUBPROTOCOLS", "RancherStreamingClient"]


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
        self._read_only = config.read_only
        self._base_url = config.url.rstrip("/")
        self._token = config.token.get_secret_value()
        self._ssl = ssl_context_from_config(config)
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

    def _refuse_unsafe(self, method: str, path: str, params: StreamParams | None) -> None:
        """The same last look the management client takes before it sends —
        this is the other place a request can leave the process."""

        refuse_unsafe_request(
            instance_name=self.instance_name,
            read_only=self._read_only,
            method=method,
            path=path,
            query_keys=[key for key, _ in normalize_params(params)],
        )

    async def stream_text_lines(
        self,
        path: str,
        *,
        params: StreamParams | None = None,
        max_lines: int = 100,
        idle_timeout_seconds: float = 2.0,
    ) -> TextLineStreamCapture:
        """Read a bounded text-line stream from a Rancher endpoint."""

        self._refuse_unsafe("GET", path, params)
        return await _stream_text_lines(
            client=self._client,
            instance_name=self.instance_name,
            path=path,
            params=normalize_params(params),
            max_lines=max_lines,
            idle_timeout_seconds=idle_timeout_seconds,
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

        self._refuse_unsafe("GET", path, params)
        return await _stream_json_lines(
            client=self._client,
            instance_name=self.instance_name,
            path=path,
            params=normalize_params(params),
            max_events=max_events,
            idle_timeout_seconds=idle_timeout_seconds,
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
        """Capture a bounded WebSocket exchange against a Rancher endpoint.

        A WebSocket can carry an exec or an attach, and messages sent over one
        are writes whatever verb opened it. So on a read-only instance it is
        refused outright when there is anything to send — and when the endpoint
        is one that acts on connecting: an exec runs its ``?command=`` before a
        single message is sent.
        """

        acts_on_connect = path.partition("?")[0].rstrip("/").endswith(_SESSION_SUBRESOURCES)
        self._refuse_unsafe("POST" if outbound_messages or acts_on_connect else "GET", path, params)
        return await _websocket_capture(
            instance_name=self.instance_name,
            base_url=self._base_url,
            token=self._token,
            ssl_context=self._ssl,
            path=path,
            params=normalize_params(params),
            subprotocols=subprotocols,
            outbound_messages=outbound_messages,
            max_messages=max_messages,
            idle_timeout_seconds=idle_timeout_seconds,
        )
