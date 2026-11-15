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
from mcp.types import CallToolResult, ImageContent, TextContent
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


# --- the three shapes the SDK hands back ------------------------------------


def test_a_bare_content_list_is_compacted_in_place() -> None:
    blocks = [_text(_INDENTED)]

    assert compact_result_text(blocks) is blocks
    assert blocks[0].text == _COMPACT


def test_a_content_and_structured_pair_leaves_the_structured_half_alone() -> None:
    structured = {"count": 2, "items": [{"name": "a"}]}
    pair = ([_text(_INDENTED)], structured)

    content, returned = compact_result_text(pair)

    assert content[0].text == _COMPACT
    assert returned is structured


def test_a_ready_made_call_tool_result_is_compacted() -> None:
    result = CallToolResult(content=[_text(_INDENTED)])

    compact_result_text(result)

    block = result.content[0]
    assert isinstance(block, TextContent)
    assert block.text == _COMPACT


def test_non_text_blocks_are_left_alone() -> None:
    image = ImageContent(type="image", data="aGk=", mimeType="image/png")
    blocks = [image, _text(_INDENTED)]

    compact_result_text(blocks)

    assert blocks[0] is image
    assert image.data == "aGk="


def test_an_unconverted_return_value_passes_straight_through() -> None:
    raw = object()

    assert compact_result_text(raw) is raw


# --- against the real server ------------------------------------------------


def test_the_sdk_still_indents_which_is_the_only_reason_this_module_exists() -> None:
    """Non-vacuity. If the SDK ever stops indenting, everything below passes
    trivially and the module is dead weight — this is what would say so."""

    tool = _TOOLS["rancher_capability_domain_list"]
    content, _ = tool.fn_metadata.convert_result(_populated(tool.fn_metadata.output_model))

    assert "\n" in content[0].text


async def test_a_real_tool_call_goes_out_compact() -> None:
    """End to end through dispatch — the only test that fails if the pass is
    written correctly but never installed."""

    content, structured = await _SERVER.call_tool("rancher_capability_domain_list", {})
    text = content[0].text

    assert "\n" not in text
    assert json.loads(text) == structured
    assert len(text) == len(json.dumps(structured, separators=(",", ":"), ensure_ascii=False))


@pytest.mark.parametrize("output", _OUTPUTS, ids=lambda output: output.tool_name)
def test_every_tools_text_block_equals_its_structured_content(output: ToolOutput) -> None:
    converted = _TOOLS[output.tool_name].fn_metadata.convert_result(_populated(output.model))

    content, structured = compact_result_text(converted)
    text = content[0].text

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
