"""AE-03: every error this server emits is valid JSON, with no prose preamble.

The server built a careful structured envelope and then MCPServer's ``Tool.run``
re-wrapped it as ``Error executing tool {name}: {envelope}``. ``JSON.parse``
fails on that, which defeats the whole point: an agent that cannot parse the
error cannot branch on ``retryable``, so it either gives up on a transient
failure or retries a permanent one forever.

``apply_bare_json_errors`` unwraps that at the tool-manager seam. These tests
cover all three ways an error can reach the client, because only one of them
passes through ``wrap_with_structured_errors`` at all.
"""

from __future__ import annotations

import json

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp.types import TextContent

from rancher_mcp.exceptions import RancherAPIError, RancherManagementPlaneUnreachableError
from rancher_mcp.tools.support.errors import (
    _TOOL_ERROR_PREFIX,
    apply_bare_json_errors,
    apply_structured_errors_to_all_tools,
)


def _build_server() -> MCPServer:
    mcp = MCPServer(name="test-errors")

    @mcp.tool()
    async def domain_failure() -> str:
        raise RancherAPIError(404, "cluster not found")

    @mcp.tool()
    async def needs_an_argument(required_thing: str) -> str:
        return required_thing

    apply_structured_errors_to_all_tools(mcp)
    apply_bare_json_errors(mcp)
    return mcp


async def _call_expecting_error(
    mcp: MCPServer, name: str, args: dict[str, object]
) -> dict[str, object]:
    with pytest.raises(ToolError) as excinfo:
        await mcp.call_tool(name, args)
    text = str(excinfo.value)
    assert not text.startswith("Error executing tool"), f"prose preamble survived: {text!r}"
    parsed = json.loads(text)  # the assertion that matters: this must not raise
    assert isinstance(parsed, dict)
    return parsed


async def test_domain_error_reaches_the_client_as_a_bare_envelope() -> None:
    """The path that DOES go through `wrap_with_structured_errors`."""

    payload = await _call_expecting_error(_build_server(), "domain_failure", {})
    assert payload["error_code"] == "API_ERROR"
    assert payload["http_status"] == 404
    assert payload["retryable"] is False


async def test_argument_validation_error_is_enveloped_too() -> None:
    """Argument validation runs in `call_fn_with_arg_validation`, BEFORE
    `tool.fn` is entered — so this error never passes through our per-tool
    wrapper and had no envelope at all until the manager-level pass."""

    payload = await _call_expecting_error(_build_server(), "needs_an_argument", {})
    assert payload["error_code"] == "MCP_ERROR"
    assert payload["retryable"] is False
    assert "required_thing" in str(payload["message"])


async def test_unknown_tool_is_enveloped_too() -> None:
    payload = await _call_expecting_error(_build_server(), "no_such_tool", {})
    assert payload["error_code"] == "MCP_ERROR"
    assert payload["tool"] == "no_such_tool"


async def test_retryable_survives_the_unwrap() -> None:
    """`retryable` is the one field an agent branches on; losing it in the
    unwrap would be worse than the preamble it replaces."""

    mcp = MCPServer(name="test-retryable")

    @mcp.tool()
    async def tunnel_down() -> str:
        raise RancherManagementPlaneUnreachableError("downstream tunnel closed")

    apply_structured_errors_to_all_tools(mcp)
    apply_bare_json_errors(mcp)

    payload = await _call_expecting_error(mcp, "tunnel_down", {})
    assert payload["error_code"] == "MANAGEMENT_PLANE_UNREACHABLE"
    assert payload["retryable"] is True
    assert payload["reason"] == "tunnel_unavailable"


def test_prefix_pattern_is_anchored_and_narrow() -> None:
    """It must strip exactly the SDK's format string and nothing resembling it,
    or we would silently truncate the front of somebody's error message."""

    assert (
        _TOOL_ERROR_PREFIX.sub("", 'Error executing tool rancher_pods_list: {"a": 1}') == '{"a": 1}'
    )
    # not at the start, and no tool name — must be left alone
    for untouched in (
        'see: Error executing tool x: {"a": 1}',
        "Error executing tool: no name here",
        '{"error_code": "API_ERROR"}',
    ):
        assert _TOOL_ERROR_PREFIX.sub("", untouched) == untouched


async def test_canary_the_sdk_still_adds_the_preamble_we_strip() -> None:
    """If a future SDK stops prefixing, `apply_bare_json_errors` becomes dead
    weight and should be removed rather than left to rot. This fails loudly at
    that moment instead of leaving a mystery wrapper in the chain."""

    mcp = MCPServer(name="test-canary")

    @mcp.tool()
    async def raises_plain_json() -> str:
        raise ToolError('{"error_code": "CANARY", "message": "x", "retryable": false}')

    with pytest.raises(ToolError) as excinfo:
        await mcp.call_tool("raises_plain_json", {})

    assert str(excinfo.value).startswith("Error executing tool raises_plain_json: "), (
        "The MCP SDK no longer prefixes tool errors — apply_bare_json_errors is "
        "now a no-op and should be deleted (and this canary with it)."
    )


async def test_a_crash_is_enveloped_without_losing_its_type() -> None:
    """The SDK reads the exception's TYPE to decide what to log.

    A return value it cannot convert is a crash, raised outside our per-tool
    wrapper as ``UnexpectedToolError`` — which the SDK logs with a traceback,
    while withholding the detail from the client. Giving the client a JSON
    envelope must not turn that into a plain ``ToolError``: the client would
    see the same thing, and the only record of what actually broke would be
    downgraded to a one-line INFO.
    """

    mcp = MCPServer(name="test-crash")

    @mcp.tool()
    async def returns_the_wrong_type() -> int:
        return "definitely not an int"  # type: ignore[return-value]

    apply_structured_errors_to_all_tools(mcp)
    apply_bare_json_errors(mcp)

    with pytest.raises(UnexpectedToolError) as excinfo:
        await mcp.call_tool("returns_the_wrong_type", {})

    payload = json.loads(str(excinfo.value))
    assert payload["error_code"] == "MCP_ERROR"
    assert payload["tool"] == "returns_the_wrong_type"
    assert "definitely not an int" not in str(excinfo.value), "crash detail reached the client"
    assert excinfo.value.__cause__ is not None, "the original exception was dropped"


@pytest.mark.parametrize("era", ["legacy", "2026-07-28"])
async def test_a_client_receives_bare_json_for_every_kind_of_failure(era: str) -> None:
    """Off the wire, in both protocol eras: whatever went wrong, the text the
    client is handed parses, and says so with ``isError``."""

    async with Client(_build_server(), mode=era) as client:
        for name in ("domain_failure", "needs_an_argument", "no_such_tool"):
            result = await client.call_tool(name, {})

            assert result.is_error is True, name
            block = result.content[0]
            assert isinstance(block, TextContent)
            assert "error_code" in json.loads(block.text), name
