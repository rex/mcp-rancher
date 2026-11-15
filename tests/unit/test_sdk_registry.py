"""Contract tests for the one module allowed to touch the MCP SDK's internals.

Every assertion here runs against a REAL ``MCPServer``. That is the whole point:
the seam's job is to be the single place that knows how the SDK's registry is
shaped, so a test that asserted against a stand-in would just move the stale
copy somewhere new. When the SDK upgrade lands, these are the tests that should
fail — and they should fail before anything else does.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from _sdk_registry_support import placeholder_tool, registry_with
from mcp import Client
from mcp.server.mcpserver import MCPServer

from rancher_mcp.sdk_registry import (
    REQUEST_METHODS,
    DispatchFn,
    RegisteredTool,
    ServerMethod,
    is_registered,
    registered_tool_names,
    registered_tools,
    wrap_dispatch,
    wrap_server_method,
)


def test_registered_tools_hands_back_the_live_objects() -> None:
    """Mutating what the seam returns must land on the real registry.

    Every post-registration pass in this server works by assigning to
    ``tool.fn`` / ``tool.title`` / ``tool.output_schema``. If the seam ever
    returned copies, all of them would silently become no-ops while still
    "succeeding".
    """

    mcp = registry_with("rancher_pods_list")

    async def replacement(cluster_id: str = "local") -> str:
        return "replaced"

    registered_tools(mcp)[0].fn = replacement

    assert registered_tools(mcp)[0].fn is replacement


def test_registered_tools_is_a_snapshot_not_a_live_view() -> None:
    """The returned list must not change underneath a pass that is iterating it."""

    mcp = registry_with("rancher_pods_list")
    snapshot = registered_tools(mcp)

    mcp.add_tool(placeholder_tool, name="rancher_nodes_list")

    assert [tool.name for tool in snapshot] == ["rancher_pods_list"]
    assert len(registered_tools(mcp)) == 2


def test_registered_tool_names_reports_the_current_registry() -> None:
    mcp = registry_with("rancher_pods_list", "rancher_nodes_list")

    assert registered_tool_names(mcp) == frozenset({"rancher_pods_list", "rancher_nodes_list"})


def test_is_registered_reads_through_rather_than_snapshotting() -> None:
    """The toolset dispatch gate calls this PER REQUEST.

    Its whole job is telling a tool the active profile removed apart from one
    that never existed, so a value captured at install time would answer for
    the wrong registry — and would answer wrongly in the direction that matters,
    reporting a removed tool as still present.
    """

    mcp = registry_with("rancher_pods_list", "rancher_nodes_list")
    assert is_registered(mcp, "rancher_nodes_list")

    mcp.remove_tool("rancher_nodes_list")

    assert not is_registered(mcp, "rancher_nodes_list")
    assert is_registered(mcp, "rancher_pods_list")
    assert not is_registered(mcp, "rancher_never_existed")


async def test_wrap_dispatch_intercepts_a_real_tool_call() -> None:
    mcp = registry_with("rancher_pods_list")
    seen: list[str] = []

    def wrap(original: DispatchFn) -> DispatchFn:
        async def call_tool(name: str, *args: Any, **kwargs: Any) -> Any:
            seen.append(name)
            return await original(name, *args, **kwargs)

        return call_tool

    wrap_dispatch(mcp, wrap)
    await mcp.call_tool("rancher_pods_list", {})

    assert seen == ["rancher_pods_list"]


async def test_wrap_dispatch_stacks_outermost_last() -> None:
    """Order is load-bearing, not incidental.

    ``register_all_tools`` installs the toolset gate BEFORE the bare-JSON error
    pass precisely so the gate ends up INSIDE it — the gate's already-structured
    envelope then travels out through the JSON pass untouched instead of being
    mistaken for prose and re-wrapped.
    """

    mcp = registry_with("rancher_pods_list")
    order: list[str] = []

    def wrap_as(label: str) -> Callable[[DispatchFn], DispatchFn]:
        def wrap(original: DispatchFn) -> DispatchFn:
            async def call_tool(name: str, *args: Any, **kwargs: Any) -> Any:
                order.append(label)
                return await original(name, *args, **kwargs)

            return call_tool

        return wrap

    wrap_dispatch(mcp, wrap_as("inner"))
    wrap_dispatch(mcp, wrap_as("outer"))
    await mcp.call_tool("rancher_pods_list", {})

    assert order == ["outer", "inner"]


# --- the routing the seam relies on, checked on the real request path -------
#
# `wrap_server_method` works only because the SDK's request handlers call back
# into the server's own public methods. That is how the SDK is built today, not
# something it promises. Calling `mcp.call_tool(...)` directly would prove
# nothing about it — these go through the SDK's own client and request runner,
# in both protocol eras, so the day a handler stops routing through the public
# method these fail instead of every interposition silently turning into a no-op.

_ERAS = ("legacy", "2026-07-28")


def _server_with_one_of_everything() -> MCPServer:
    mcp = registry_with("rancher_pods_list")

    @mcp.prompt()
    def greet(who: str = "operator") -> str:  # pyright: ignore[reportUnusedFunction]
        return f"hello {who}"

    @mcp.resource("probe://static")
    def static() -> str:  # pyright: ignore[reportUnusedFunction]
        return "static"

    @mcp.resource("probe://item/{item}")
    def item(item: str) -> str:  # pyright: ignore[reportUnusedFunction]
        return item

    return mcp


@pytest.mark.parametrize("era", _ERAS)
async def test_a_tool_call_off_the_wire_goes_through_wrap_dispatch(era: str) -> None:
    mcp = registry_with("rancher_pods_list")
    seen: list[str] = []

    def wrap(original: DispatchFn) -> DispatchFn:
        async def call_tool(name: str, *args: Any, **kwargs: Any) -> Any:
            seen.append(name)
            return await original(name, *args, **kwargs)

        return call_tool

    wrap_dispatch(mcp, wrap)
    async with Client(mcp, mode=era) as client:
        result = await client.call_tool("rancher_pods_list", {})

    assert seen == ["rancher_pods_list"]
    assert result.is_error is False


@pytest.mark.parametrize("era", _ERAS)
async def test_every_request_method_is_what_the_wire_dispatches_through(era: str) -> None:
    """One interposition per method in ``REQUEST_METHODS``, then one real
    request of each kind. A method the wire does not route through would be a
    hole in the entrypoint's startup gate: that request would be answered out
    of a registry that is still loading."""

    mcp = _server_with_one_of_everything()
    reached: set[str] = set()

    def record(method_name: str) -> Callable[[ServerMethod], ServerMethod]:
        def wrap(method: ServerMethod) -> ServerMethod:
            async def recorded(*args: Any, **kwargs: Any) -> Any:
                reached.add(method_name)
                return await method(*args, **kwargs)

            return recorded

        return wrap

    for method_name in REQUEST_METHODS:
        wrap_server_method(mcp, method_name, record(method_name))

    async with Client(mcp, mode=era) as client:
        await client.list_tools()
        await client.call_tool("rancher_pods_list", {})
        await client.list_prompts()
        await client.get_prompt("greet", {"who": "pierce"})
        await client.list_resources()
        await client.list_resource_templates()
        await client.read_resource("probe://static")

    assert reached == set(REQUEST_METHODS)


def test_request_methods_names_real_public_methods() -> None:
    """A typo here would raise at startup; say so in a test instead."""

    mcp = MCPServer(name="request-methods-probe")

    for method_name in REQUEST_METHODS:
        assert not method_name.startswith("_")
        assert callable(getattr(mcp, method_name)), method_name


@pytest.mark.parametrize("name", sorted(RegisteredTool.__annotations__))
def test_registered_tool_protocol_matches_the_real_sdk_tool(name: str) -> None:
    """Every field the seam's ``RegisteredTool`` promises must really exist.

    The Protocol is structural, so nothing type-checks it against the SDK's
    concrete class — a field could be renamed upstream and the seam would keep
    claiming it until something read it at runtime, deep inside a pass.

    The field list is read off the Protocol itself. It used to be written out
    by hand here, and so went stale the first time the Protocol grew.
    """

    tool: Any = registered_tools(registry_with("rancher_pods_list"))[0]

    assert hasattr(tool, name), f"the SDK's tool object no longer has `{name}`"
