"""An argument that carries JSON as text accepts JSON as text.

**The defect this gates.** The generic tools take ``payload_json``,
``params_json`` and ``filters_json`` as JSON text. Before validating a call,
the SDK JSON-decodes every string argument whose annotation is not exactly
``str`` — so an *optional* one (``str | None``) arrived as a dict and failed
validation as a string. Through MCP, every optional JSON-text argument
refused every object it was given, for as long as the tools existed:
``rancher_norman_resource_list(params_json='{"limit": 5}')`` never worked.

**Why nothing noticed.** Every test of these tools called the Python function
directly, where no decoding happens. The request path was never asked. One
test even passed *because* of the bug: it looked for the word ``action`` in a
refusal, and found it in the SDK's complaint about the dict it had made.

So this asks the request path, of every tool that has such an argument.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from _output_schema_dump_parity_support import build_registered_server
from _plausible_arguments_support import plausible_arguments
from _write_guards_support import Observation, observe_call
from mcp.server.mcpserver import MCPServer
from pydantic import TypeAdapter

from rancher_mcp import rate_limit
from rancher_mcp.config import clear_settings_cache, clear_toolset_settings_cache
from rancher_mcp.sdk_registry import registered_tools
from rancher_mcp.tools.support.annotations import READ_ONLY
from rancher_mcp.tools.support.json_args import OptionalJsonText

_SERVER = build_registered_server()
_TOOLS = {tool.name: tool for tool in registered_tools(_SERVER)}
_TARGETS = sorted(
    (name, argument)
    for name, tool in _TOOLS.items()
    for argument in tool.parameters.get("properties", {})
    if argument.endswith("_json")
)
_OBJECT_AS_TEXT = '{"metadata": {"name": "x"}}'


def _reset() -> None:
    clear_settings_cache()
    clear_toolset_settings_cache()
    rate_limit.reset_rate_limit_state()


@pytest.fixture(autouse=True)
def _writable_instance(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("RANCHER_READ_ONLY", "false")
    _reset()
    yield
    _reset()


def _refused_as_malformed(seen: Observation) -> bool:
    return seen.is_error and "validation error" in seen.message


def test_the_gate_has_real_targets() -> None:
    assert len(_TARGETS) >= 20, _TARGETS
    assert ("rancher_norman_resource_list", "params_json") in _TARGETS
    assert ("rancher_steve_resource_delete", "payload_json") in _TARGETS


@pytest.mark.parametrize(("tool_name", "argument"), _TARGETS)
async def test_every_json_text_argument_accepts_an_object_as_text(
    tool_name: str, argument: str
) -> None:
    arguments = plausible_arguments(tool_name, _TOOLS[tool_name].parameters)
    arguments[argument] = _OBJECT_AS_TEXT

    seen = await observe_call(_SERVER, tool_name, arguments)

    assert not _refused_as_malformed(seen), (
        f"{tool_name} refused {argument}={_OBJECT_AS_TEXT!r} before the tool ran:\n"
        f"  {seen.message}\n\n"
        "The SDK decoded the text into an object and then rejected the object as a string. "
        "Annotate the argument `OptionalJsonText` (rancher_mcp.tools.support.json_args)."
    )


async def test_the_gate_catches_an_argument_the_sdk_decodes() -> None:
    """Non-vacuity: the original defect, planted, is refused before it runs."""

    mcp = MCPServer(name="json-text-probe", instructions="probe")

    @mcp.tool(name="rancher_plain_optional", annotations=READ_ONLY)
    async def rancher_plain_optional(params_json: str | None = None) -> str:  # pyright: ignore[reportUnusedFunction]
        return "ran"

    seen = await observe_call(mcp, "rancher_plain_optional", {"params_json": _OBJECT_AS_TEXT})

    assert seen.is_error, "the SDK no longer decodes optional strings — this gate can go"


async def test_the_text_reaches_the_request_as_it_was_given() -> None:
    seen = await observe_call(
        _SERVER,
        "rancher_norman_resource_list",
        {"schema_id": "project", "params_json": '{"name": "shop"}', "filters_json": '{"x": "y"}'},
    )

    assert not seen.is_error, seen.envelope
    assert {"name", "x"} <= set(seen.query_keys), seen.query_keys


async def test_a_client_that_sends_the_object_itself_is_accepted_too() -> None:
    seen = await observe_call(
        _SERVER,
        "rancher_norman_resource_list",
        {"schema_id": "project", "params_json": {"name": "shop"}},
    )

    assert not seen.is_error, seen.envelope
    assert "name" in seen.query_keys


@pytest.mark.parametrize(
    ("given", "validated"),
    [
        ({"limit": 5}, '{"limit": 5}'),
        ([1, "a"], '[1, "a"]'),
        ('{"limit": 5}', '{"limit": 5}'),
        ("not json", "not json"),
        (None, None),
    ],
)
def test_only_a_decoded_object_or_array_is_re_encoded(given: object, validated: object) -> None:
    assert TypeAdapter(OptionalJsonText).validate_python(given) == validated


def test_the_published_schema_is_that_of_an_optional_string() -> None:
    assert (
        TypeAdapter(OptionalJsonText).json_schema()
        == TypeAdapter[str | None](str | None).json_schema()
    )
