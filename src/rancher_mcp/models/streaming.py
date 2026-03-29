"""Streaming and WebSocket client data models."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def _empty_event_list() -> list[dict[str, object]]:
    """Return a typed empty event list."""

    return []


def _empty_frame_list() -> list["WebSocketFrame"]:
    """Return a typed empty WebSocket-frame list."""

    return []


class TextLineStreamCapture(RancherModel):
    """Captured text-line stream from a Rancher HTTP endpoint."""

    instance: str
    path: str
    line_count: int
    truncated: bool = False
    lines: list[str] = Field(default_factory=list)


class JSONEventStreamCapture(RancherModel):
    """Captured JSON-line stream from a Rancher HTTP endpoint."""

    instance: str
    path: str
    event_count: int
    truncated: bool = False
    events: list[dict[str, object]] = Field(default_factory=_empty_event_list)


class WebSocketFrame(RancherModel):
    """Captured WebSocket frame with optional Kubernetes channel decoding."""

    opcode: str
    byte_length: int
    channel_id: int | None = None
    channel_name: str | None = None
    text: str | None = None


class WebSocketCapture(RancherModel):
    """Captured WebSocket exchange against a Rancher proxied endpoint."""

    instance: str
    path: str
    negotiated_subprotocol: str | None = None
    frame_count: int
    truncated: bool = False
    frames: list[WebSocketFrame] = Field(default_factory=_empty_frame_list)
