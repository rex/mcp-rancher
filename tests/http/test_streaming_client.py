"""HTTP and WebSocket boundary tests for the streaming client."""

from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr
from websockets.asyncio.server import Request, Response, ServerConnection, serve

from rancher_mcp.clients.streaming import (
    KUBERNETES_STREAM_SUBPROTOCOLS,
    RancherStreamingClient,
)
from rancher_mcp.models.discovery import RancherInstanceConfig


def build_config(url: str) -> RancherInstanceConfig:
    """Create deterministic instance config for streaming tests."""

    return RancherInstanceConfig(
        url=url,
        token=SecretStr("token-xxxxx:yyyyyyyyy"),
        verify_ssl=True,
        read_only=False,
    )


@pytest.mark.asyncio
async def test_stream_text_lines_reads_bounded_http_lines() -> None:
    """Text streaming should preserve non-empty lines and stringify query params."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert (
            request.url.path == "/k8s/clusters/venue-local/api/v1/namespaces/default/pods/demo/log"
        )
        assert request.url.query == b"follow=true&tailLines=2"
        return httpx.Response(200, text="first\n\nsecond\n")

    transport = httpx.MockTransport(handler)
    async with RancherStreamingClient(
        "work",
        build_config("https://rancher.work.example.com"),
        transport=transport,
    ) as client:
        result = await client.stream_text_lines(
            "/k8s/clusters/venue-local/api/v1/namespaces/default/pods/demo/log",
            params={"follow": True, "tailLines": 2},
            max_lines=2,
        )

    assert result.line_count == 2
    assert result.lines == ["first", "second"]
    assert result.truncated is True


@pytest.mark.asyncio
async def test_stream_json_lines_parses_watch_events() -> None:
    """JSON-line streaming should decode watch-style event payloads."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.query == b"watch=true&timeoutSeconds=5"
        return httpx.Response(
            200,
            text=(
                '{"type":"ADDED","object":{"metadata":{"name":"demo"}}}\n'
                '{"type":"MODIFIED","object":{"metadata":{"name":"demo"}}}\n'
            ),
        )

    transport = httpx.MockTransport(handler)
    async with RancherStreamingClient(
        "work",
        build_config("https://rancher.work.example.com"),
        transport=transport,
    ) as client:
        result = await client.stream_json_lines(
            "/k8s/clusters/venue-local/api/v1/namespaces/default/pods",
            params={"watch": True, "timeoutSeconds": 5},
            max_events=2,
        )

    assert result.event_count == 2
    assert result.events[0]["type"] == "ADDED"
    assert result.events[1]["type"] == "MODIFIED"
    assert result.truncated is True


@pytest.mark.asyncio
async def test_stream_text_lines_retries_transient_transport_errors() -> None:
    """Text streaming should retry transient transport failures before succeeding."""

    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadError("transient stream failure", request=request)
        return httpx.Response(200, text="first\nsecond\n")

    transport = httpx.MockTransport(handler)
    async with RancherStreamingClient(
        "work",
        build_config("https://rancher.work.example.com"),
        transport=transport,
    ) as client:
        result = await client.stream_text_lines(
            "/k8s/clusters/venue-local/api/v1/namespaces/default/pods/demo/log",
            max_lines=5,
        )

    assert attempts == 2
    assert result.line_count == 2
    assert result.lines == ["first", "second"]
    assert result.truncated is False


@pytest.mark.asyncio
async def test_websocket_capture_negotiates_subprotocol_and_decodes_channels() -> None:
    """WebSocket capture should preserve auth, params, and Kubernetes channel frames."""

    observed_paths: list[str] = []
    observed_auth: list[str | None] = []

    async def process_request(
        _connection: ServerConnection,
        request: Request,
    ) -> Response | None:
        observed_paths.append(request.path)
        observed_auth.append(request.headers.get("Authorization"))
        return None

    async def handler(connection: ServerConnection) -> None:
        await connection.send(b"\x01exec-ok\n")
        await connection.send(b"\x02warn\n")
        await connection.close()

    async with serve(
        handler,
        "127.0.0.1",
        0,
        subprotocols=["v4.channel.k8s.io"],
        process_request=process_request,
    ) as server:
        sockets = server.sockets
        assert sockets is not None
        port = sockets[0].getsockname()[1]

        async with RancherStreamingClient(
            "lab",
            build_config(f"http://127.0.0.1:{port}"),
        ) as client:
            result = await client.websocket_capture(
                "/k8s/clusters/venue-local/api/v1/namespaces/default/pods/demo/exec",
                params=[
                    ("stdout", True),
                    ("stderr", True),
                    ("command", "echo"),
                    ("command", "hello"),
                ],
                subprotocols=KUBERNETES_STREAM_SUBPROTOCOLS,
                max_messages=2,
            )

    assert observed_paths == [
        "/k8s/clusters/venue-local/api/v1/namespaces/default/pods/demo/exec"
        "?stdout=true&stderr=true&command=echo&command=hello"
    ]
    assert observed_auth == ["Bearer token-xxxxx:yyyyyyyyy"]
    assert result.negotiated_subprotocol == "v4.channel.k8s.io"
    assert result.frame_count == 2
    assert [frame.channel_name for frame in result.frames] == ["stdout", "stderr"]
    assert [frame.text for frame in result.frames] == ["exec-ok\n", "warn\n"]
