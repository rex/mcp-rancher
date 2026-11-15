"""Send the text half of every tool result as compact JSON.

A structured tool result goes out twice: once as ``structuredContent``, and
once as a text block for clients that predate it. The SDK renders that text
block with ``indent=2``, which is pure whitespace — measured on
``rancher_capability_domain_list`` it is 3,989 characters against 2,723
compact, **+46%**.

Who pays is not symmetrical, which is why this went unnoticed. Claude Code
feeds the model ``JSON.stringify(structuredContent)`` and drops text blocks
outright, so there the indentation is free. Every client that reads ``content``
instead pays for it on every single response — and those are precisely the
small-context hosts the footprint work was done for.
``tests/unit/test_ae10_response_size.py`` had been budgeting the compact form
all along; the text block was simply never the thing being measured.

The two representations must stay *equivalent in meaning*, not merely similar.
A client flag can flip Claude Code to prefer ``content``, so neither may be the
degraded copy. That is why this re-renders the text block's own JSON rather
than substituting ``structuredContent`` for it: for a tool whose return value
the SDK has to wrap (``{"result": [...]}``), the two legitimately differ in
shape, and substituting would silently change what a text-reading client sees.

``schema_compaction.py`` is the sibling of this module: that one trims what we
*publish* about a tool, this one trims what a tool *returns*.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.types import CallToolResult, TextContent

from rancher_mcp.sdk_registry import DispatchFn, wrap_dispatch


def compact_json_text(text: str) -> str:
    """Re-render an indented JSON document on one line; return anything else as-is.

    Deliberately narrow. Only a document that opens with ``{`` or ``[`` *and*
    contains a newline is touched: that is exactly what an ``indent=2`` render
    of a non-empty container looks like, and nothing else. Pod logs, prose, an
    already-compact payload and a bare scalar all pass through untouched, as
    does anything that merely looks like JSON and fails to parse.
    """

    if "\n" not in text or text.lstrip()[:1] not in ("{", "["):
        return text
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    # ensure_ascii=False: the SDK writes UTF-8 through, and escaping it to
    # \uXXXX here would make a non-ASCII payload *larger* than it arrived.
    return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)


def compact_result_text(result: Any) -> Any:
    """Compact the text blocks of one dispatch result, in place.

    Dispatch hands back a ``CallToolResult``, or — when a tool still needs an
    answer from the person — an ``InputRequiredResult``, which carries no
    content yet and is returned untouched, as is anything else.
    """

    # Inspect through an `object`-typed alias: narrowing `result` itself would
    # turn the `Any` this returns into a partially-unknown union under strict.
    shape: object = result
    if isinstance(shape, CallToolResult):
        for block in shape.content:
            if isinstance(block, TextContent):
                block.text = compact_json_text(block.text)
    return result


def apply_compact_result_text(mcp: Any) -> None:
    """Compact every successful tool result's text blocks on the way out.

    Interposes on dispatch rather than wrapping each tool: the text block does
    not exist until the SDK has converted the tool's return value, which
    happens after the tool function — and every wrapper around it — returns.
    Failures raise past this untouched; their envelopes are built elsewhere.

    Construction time only, never per request.
    """

    def wrap(original_call_tool: DispatchFn) -> DispatchFn:
        async def call_tool(name: str, *args: Any, **kwargs: Any) -> Any:
            return compact_result_text(await original_call_tool(name, *args, **kwargs))

        return call_tool

    wrap_dispatch(mcp, wrap)
