"""AE-03: every error this server emits is valid JSON, with no prose preamble.

The server built a careful structured envelope and then FastMCP's ``Tool.run``
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
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from rancher_mcp.exceptions import RancherAPIError, RancherManagementPlaneUnreachableError
from rancher_mcp.tools.support.errors import (
    _TOOL_ERROR_PREFIX,
    apply_bare_json_errors,
    apply_structured_errors_to_all_tools,
)


def _build_server() -> FastMCP:
    mcp = FastMCP(name="test-errors")

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
    mcp: FastMCP, name: str, args: dict[str, object]
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

    mcp = FastMCP(name="test-retryable")

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

    mcp = FastMCP(name="test-canary")

    @mcp.tool()
    async def raises_plain_json() -> str:
        raise ToolError('{"error_code": "CANARY", "message": "x", "retryable": false}')

    with pytest.raises(ToolError) as excinfo:
        await mcp.call_tool("raises_plain_json", {})

    assert str(excinfo.value).startswith("Error executing tool raises_plain_json: "), (
        "The MCP SDK no longer prefixes tool errors — apply_bare_json_errors is "
        "now a no-op and should be deleted (and this canary with it)."
    )
