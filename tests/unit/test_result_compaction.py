"""The text half of a tool result is compact JSON, and still says the same thing.

Two properties are gated here, and the second matters more than the first:

1. **Compact.** The SDK renders a result's text block with ``indent=2`` —
   +46% on a real response, all of it whitespace, paid by every client that
   reads ``content`` rather than ``structuredContent``.
2. **Equivalent.** The text block and ``structuredContent`` must mean the same
   thing for every tool. Claude Code reads one, most other clients read the
   other, and a client-side flag can swap which one Claude Code prefers — so a
   divergence would not be a formatting bug, it would be two clients being
   told different things by the same call.

The fleet-wide check runs the SDK's *own* conversion on a maximally populated
instance of every tool's output model, rather than re-deriving what the SDK
would produce. That is deliberate: a hand-rolled dump would agree with itself
forever, including after the SDK changed how it renders.
"""

from __future__ import annotations

import json

import pytest
from _output_schema_dump_parity_support import (
    ToolOutput,
    build_registered_server,
    iter_tool_outputs,
    synthesize_example,
)
from mcp import Client
from mcp.types import CallToolResult, ImageContent, InputRequiredResult, TextContent
from pydantic import BaseModel

from rancher_mcp.result_compaction import compact_json_text, compact_result_text
from rancher_mcp.sdk_registry import registered_tools

_SERVER = build_registered_server()
_TOOLS = {tool.name: tool for tool in registered_tools(_SERVER)}
_OUTPUTS = iter_tool_outputs(_SERVER)

_INDENTED = '{\n  "count": 2,\n  "items": [\n    {\n      "name": "a"\n    }\n  ]\n}'
_COMPACT = '{"count":2,"items":[{"name":"a"}]}'


def _text(value: str) -> TextContent:
    return TextContent(type="text", text=value)


def _populated(model: type[BaseModel]) -> BaseModel:
    schema = model.model_json_schema(mode="validation")
    return model.model_validate(synthesize_example(schema, schema.get("$defs", {})))


# --- the pure function ------------------------------------------------------


def test_an_indented_document_is_rendered_on_one_line() -> None:
    assert compact_json_text(_INDENTED) == _COMPACT


def test_an_indented_array_is_rendered_on_one_line() -> None:
    assert compact_json_text('[\n  1,\n  "two"\n]') == '[1,"two"]'


def test_key_order_survives() -> None:
    """Order is not meaning in JSON, but a model reads top to bottom, and the
    envelope puts the summary before the items on purpose."""

    out = compact_json_text('{\n  "zeta": 1,\n  "alpha": 2\n}')

    assert out == '{"zeta":1,"alpha":2}'


def test_non_ascii_is_written_through_not_escaped() -> None:
    """Escaping to ``\\uXXXX`` would make the payload *larger* than it arrived."""

    assert compact_json_text('{\n  "name": "café-日本"\n}') == '{"name":"café-日本"}'


@pytest.mark.parametrize(
    "text",
    [
        "plain prose",
        "2026-11-15T03:00:00Z starting\n2026-11-15T03:00:01Z ready",  # pod logs
        '{"already":"compact"}',
        "{ this only looks\n like JSON }",
        '"a bare string"',
        "42",
        "",
        "   ",
    ],
)
def test_anything_that_is_not_an_indented_document_is_returned_untouched(text: str) -> None:
    """Identity, not equality: these must not even be re-rendered."""

    assert compact_json_text(text) is text


# --- what dispatch hands back ------------------------------------------------


def test_a_call_tool_result_is_compacted_in_place() -> None:
    structured = {"count": 2, "items": [{"name": "a"}]}
    result = CallToolResult(content=[_text(_INDENTED)], structured_content=structured)

    assert compact_result_text(result) is result

    block = result.content[0]
    assert isinstance(block, TextContent)
    assert block.text == _COMPACT
    assert result.structured_content is structured


def test_non_text_blocks_are_left_alone() -> None:
    image = ImageContent(type="image", data="aGk=", mime_type="image/png")
    result = CallToolResult(content=[image, _text(_INDENTED)])

    compact_result_text(result)

    assert result.content[0] is image
    assert image.data == "aGk="


def test_a_result_still_waiting_on_the_person_passes_straight_through() -> None:
    """An ``InputRequiredResult`` has no content yet — there is nothing to
    compact, and it must reach the client exactly as the SDK built it."""

    pending = InputRequiredResult(request_state="opaque")

    assert compact_result_text(pending) is pending


def test_anything_else_passes_straight_through() -> None:
    raw = object()

    assert compact_result_text(raw) is raw


# --- against the real server ------------------------------------------------


def test_the_sdk_still_indents_which_is_the_only_reason_this_module_exists() -> None:
    """Non-vacuity. If the SDK ever stops indenting, everything below passes
    trivially and the module is dead weight — this is what would say so."""

    tool = _TOOLS["rancher_capability_domain_list"]
    result = tool.fn_metadata.convert_result(_populated(tool.fn_metadata.output_model))

    assert "\n" in result.content[0].text


async def test_a_real_tool_call_goes_out_compact() -> None:
    """End to end through dispatch — the only test that fails if the pass is
    written correctly but never installed."""

    result = await _SERVER.call_tool("rancher_capability_domain_list", {})
    text = result.content[0].text
    structured = result.structured_content

    assert "\n" not in text
    assert json.loads(text) == structured
    assert len(text) == len(json.dumps(structured, separators=(",", ":"), ensure_ascii=False))


@pytest.mark.parametrize("era", ["legacy", "2026-07-28"])
async def test_a_client_receives_the_compact_text_in_both_eras(era: str) -> None:
    """The same, but off the wire: through the SDK's client and request runner
    rather than a direct call, so it also proves the request path reaches the
    interposition at all."""

    async with Client(_SERVER, mode=era) as client:
        result = await client.call_tool("rancher_capability_domain_list", {})

    text = result.content[0].text
    assert "\n" not in text
    assert json.loads(text) == result.structured_content


@pytest.mark.parametrize("output", _OUTPUTS, ids=lambda output: output.tool_name)
def test_every_tools_text_block_equals_its_structured_content(output: ToolOutput) -> None:
    converted = _TOOLS[output.tool_name].fn_metadata.convert_result(_populated(output.model))

    result = compact_result_text(converted)
    text = result.content[0].text
    structured = result.structured_content

    assert "\n" not in text
    assert json.loads(text) == structured, (
        f"{output.tool_name}: the text block and structuredContent disagree, so a client "
        "reading `content` and one reading `structuredContent` are told different things"
    )


async def test_the_instances_resource_body_is_compact_too() -> None:
    contents = await _SERVER.read_resource("rancher://instances")
    body = next(iter(contents)).content

    assert isinstance(body, str)
    assert "\n" not in body
    assert isinstance(json.loads(body), dict)
