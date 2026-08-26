"""Contract tests for the one module allowed to touch the MCP SDK's internals.

Every assertion here runs against a REAL ``FastMCP``. That is the whole point:
the seam's job is to be the single place that knows how the SDK's registry is
shaped, so a test that asserted against a stand-in would just move the stale
copy somewhere new. When the SDK upgrade lands, these are the tests that should
fail — and they should fail before anything else does.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import mcp.types as types
import pytest
from _sdk_registry_support import placeholder_tool, registry_with
from mcp.server.fastmcp import FastMCP

from rancher_mcp.sdk_registry import (
    DispatchFn,
    advertised_server_version,
    install_list_tools_handler,
    installed_list_tools_handler,
    is_registered,
    registered_tool_names,
    registered_tools,
    stamp_server_version,
    wrap_dispatch,
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


def test_server_version_round_trips_to_what_a_client_is_told() -> None:
    mcp = FastMCP(name="version-test")
    before = advertised_server_version(mcp)

    stamp_server_version(mcp, "9.9.9")

    assert before != "9.9.9"
    assert advertised_server_version(mcp) == "9.9.9"


async def test_install_list_tools_handler_displaces_the_sdk_handler() -> None:
    """The two-phase startup is only correct if this actually displaces.

    A silent no-op here would leave ``tools/list`` racing the background tool
    loader — answering with a partially registered surface, which is exactly
    what the two-phase design exists to prevent, and which would look like a
    flaky client rather than a bug here.
    """

    mcp = registry_with("rancher_pods_list")
    sdk_handler = installed_list_tools_handler(mcp)
    assert sdk_handler is not None, "FastMCP should register a tools/list handler itself"

    called: list[bool] = []

    async def handler() -> list[Any]:
        called.append(True)
        return []

    install_list_tools_handler(mcp, handler)
    ours = installed_list_tools_handler(mcp)
    assert ours is not sdk_handler

    await ours(types.ListToolsRequest(method="tools/list"))
    assert called == [True]


@pytest.mark.parametrize(
    "name",
    ["fn", "fn_metadata", "name", "output_schema", "parameters", "title"],
)
def test_registered_tool_protocol_matches_the_real_sdk_tool(name: str) -> None:
    """Every field the seam's ``RegisteredTool`` promises must really exist.

    The Protocol is structural, so nothing type-checks it against the SDK's
    concrete class — a field could be renamed upstream and the seam would keep
    claiming it until something read it at runtime, deep inside a pass.
    """

    tool: Any = registered_tools(registry_with("rancher_pods_list"))[0]

    assert hasattr(tool, name), f"the SDK's tool object no longer has `{name}`"
