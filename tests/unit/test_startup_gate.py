"""The entrypoint serves before its tools have loaded; nothing may be answered
out of a half-built registry.

``__main__`` starts the server as soon as it can answer a client's first
message, and registers every tool, prompt and resource on a background thread.
``hold_requests_until`` is what makes that safe. These tests drive it the way a
client does — through the SDK's own client and request runner, in both
protocol eras — because the property that matters is what a client is *told*,
and a direct call to a patched method would say nothing about whether the
request path ever reaches the patch.

Three things are pinned:

* the first message is NOT held — connecting has to succeed with nothing
  loaded, or the fast path buys nothing;
* everything after it IS held, and then answered in full — including prompts,
  which a client lists in parallel with tools and has no reason to ask for
  twice;
* a registry that never arrives fails the request, rather than answering with
  an empty list that looks like a real one.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import pytest
from _sdk_registry_support import placeholder_tool
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.shared.exceptions import MCPError

from rancher_mcp.sdk_registry import DispatchFn, wrap_dispatch
from rancher_mcp.server import hold_requests_until, new_server

_ERAS = ("legacy", "2026-07-28")


def _register_late(mcp: MCPServer, ready: threading.Event, *, after: float) -> threading.Thread:
    """Register one tool and one prompt on a thread, the way the entrypoint's
    loader does, after a delay long enough for requests to arrive first."""

    def load() -> None:
        time.sleep(after)
        mcp.add_tool(placeholder_tool, name="rancher_pods_list")

        @mcp.prompt()
        def rancher_diagnose_cluster() -> str:  # pyright: ignore[reportUnusedFunction]
            return "diagnose"

        ready.set()

    return threading.Thread(target=load, daemon=True)


@pytest.mark.parametrize("era", _ERAS)
async def test_connecting_does_not_wait_for_the_registry(era: str) -> None:
    mcp = new_server("startup-gate-probe", "probe")
    hold_requests_until(mcp, threading.Event(), timeout=30)

    started = time.monotonic()
    async with Client(mcp, mode=era) as client:
        connected_in = time.monotonic() - started
        assert client.protocol_version

    assert connected_in < 5, (
        f"connecting took {connected_in:.1f}s with the registry not ready — the first "
        "message is being held, which defeats the whole point of serving early"
    )


@pytest.mark.parametrize("era", _ERAS)
async def test_requests_wait_for_the_registry_and_are_then_answered_in_full(era: str) -> None:
    mcp = new_server("startup-gate-probe", "probe")
    ready = threading.Event()
    hold_requests_until(mcp, ready, timeout=10)
    loader = _register_late(mcp, ready, after=0.3)

    async with Client(mcp, mode=era) as client:
        loader.start()
        # Fired together and before the loader finishes, exactly as a client
        # does right after connecting.
        tools, prompts = await asyncio.gather(client.list_tools(), client.list_prompts())

    assert [tool.name for tool in tools.tools] == ["rancher_pods_list"]
    assert [prompt.name for prompt in prompts.prompts] == ["rancher_diagnose_cluster"], (
        "prompts were answered before the registry finished loading; a client lists them "
        "once, straight after connecting, so an early empty answer is a permanent one"
    )


@pytest.mark.parametrize("era", _ERAS)
async def test_a_tool_call_that_arrives_before_the_registry_is_held_too(era: str) -> None:
    """The protocol is stateless: a resumed session may call a tool it listed
    in an earlier connection, before listing anything in this one."""

    mcp = new_server("startup-gate-probe", "probe")
    ready = threading.Event()
    hold_requests_until(mcp, ready, timeout=10)
    loader = _register_late(mcp, ready, after=0.3)

    async with Client(mcp, mode=era) as client:
        loader.start()
        result = await client.call_tool("rancher_pods_list", {})

    assert result.is_error is False


@pytest.mark.parametrize("era", _ERAS)
async def test_a_call_parked_during_loading_gets_what_loading_installed(era: str) -> None:
    """The loader installs call-level passes — the toolset gate, the JSON error
    envelope, compact text — on top of the hold, while early requests are
    already parked inside it.

    A parked request has to come out through those passes like any later one.
    Resuming on the method captured before they existed would answer one early
    caller under different rules from everyone after it — prose where the
    contract promises a JSON error, say — and only when startup is slow enough
    for a request to arrive first, which is exactly when nobody is watching.
    """

    mcp = new_server("startup-gate-probe", "probe")
    ready = threading.Event()
    hold_requests_until(mcp, ready, timeout=10)
    dispatched: list[str] = []

    def record(dispatch: DispatchFn) -> DispatchFn:
        async def recording(name: str, *args: Any, **kwargs: Any) -> Any:
            dispatched.append(name)
            return await dispatch(name, *args, **kwargs)

        return recording

    def load() -> None:
        time.sleep(0.3)
        mcp.add_tool(placeholder_tool, name="rancher_pods_list")
        wrap_dispatch(mcp, record)
        ready.set()

    loader = threading.Thread(target=load, daemon=True)

    async with Client(mcp, mode=era) as client:
        loader.start()
        result = await client.call_tool("rancher_pods_list", {})

    assert result.is_error is False
    assert dispatched == ["rancher_pods_list"], (
        f"a call parked while the registry loaded was dispatched {len(dispatched)} time(s) "
        "through a pass installed during loading — it must go through exactly once, "
        "the same as a call that arrives afterwards"
    )


@pytest.mark.parametrize("era", _ERAS)
async def test_a_registry_that_never_loads_fails_the_request(era: str) -> None:
    """Never an empty answer: a client may cache an empty tool list, and has no
    way to tell it from a server that genuinely offers nothing."""

    mcp = new_server("startup-gate-probe", "probe")
    hold_requests_until(mcp, threading.Event(), timeout=0.05)

    async with Client(mcp, mode=era) as client:
        with pytest.raises(MCPError) as excinfo:
            await client.list_tools()

    assert "still registering" in str(excinfo.value)


async def test_once_ready_requests_are_not_delayed() -> None:
    mcp = new_server("startup-gate-probe", "probe")
    ready = threading.Event()
    ready.set()
    hold_requests_until(mcp, ready, timeout=30)
    mcp.add_tool(placeholder_tool, name="rancher_pods_list")

    started = time.monotonic()
    tools = await mcp.list_tools()

    assert [tool.name for tool in tools] == ["rancher_pods_list"]
    assert time.monotonic() - started < 1
