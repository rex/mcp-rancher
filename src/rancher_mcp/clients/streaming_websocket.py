"""WebSocket capture helpers for the Rancher streaming client."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import cast

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed
from websockets.typing import Subprotocol

from rancher_mcp.clients.streaming_transport import websocket_url
from rancher_mcp.models.streaming import WebSocketCapture, WebSocketFrame

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


async def websocket_capture(
    *,
    instance_name: str,
    base_url: str,
    token: str,
    ssl_context: object,
    path: str,
    params: tuple[tuple[str, str], ...],
    subprotocols: Sequence[Subprotocol] | None,
    outbound_messages: Sequence[WebSocketMessage] | None,
    max_messages: int,
    idle_timeout_seconds: float,
) -> WebSocketCapture:
    """Capture a bounded WebSocket exchange against a Rancher endpoint."""

    resolved_url = websocket_url(base_url, path, params)
    frames: list[WebSocketFrame] = []
    truncated = False

    async with connect(
        resolved_url,
        additional_headers={"Authorization": f"Bearer {token}"},
        subprotocols=tuple(subprotocols) if subprotocols else None,
        open_timeout=10,
        close_timeout=2,
        ssl=ssl_context,
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

            frames.append(frame_from_message(raw_message))
        else:
            truncated = True

        negotiated_subprotocol = websocket.subprotocol

    return WebSocketCapture(
        instance=instance_name,
        path=path,
        negotiated_subprotocol=negotiated_subprotocol,
        frame_count=len(frames),
        truncated=truncated,
        frames=frames,
    )


def frame_from_message(message: WebSocketMessage) -> WebSocketFrame:
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
