"""The context-footprint budget — a ratchet on what this server costs a client.

WHY THIS EXISTS. Every other gate in this repo guards correctness. This one
guards a resource that was never measured and therefore grew unchecked: the
bytes a client must ingest just to LEARN the server exists.

Measured 2026-08-22, before any reduction work: **781.8 KB / ~200,137 tokens**
across 321 tools. That is 156% of a 128k context window and 625% of a 32k local
model's — a model with a 32k window could not connect at all, because the tool
list alone was six times its entire memory. Composition was 64.2% `outputSchema`,
20.9% `inputSchema`, and only 8.3% descriptions — i.e. the field that actually
drives tool selection was the smallest line item.

The root cause was structural, not incidental: codegen made adding a tool nearly
free, and tool COUNT was treated as a feature (advertised in the README, pinned
by a manifest gate). 321 tools resolved to ~4 distinct shapes across 43 resource
families; 120 of them carried no semantics beyond a noun. Pruning alone would
have regrown. This gate is the missing feedback signal — the thing that makes a
new tool cost something visible.

HOW TO USE IT. The budgets below are a RATCHET. They may be lowered freely as
the surface improves. Raising one is a deliberate act: do it only with a comment
saying what was added and why it earns the bytes, in the same commit. A failure
here is not a bug to route around — it means the surface grew, and the question
to answer is whether the new tool tells a model something the generic
`rancher_{norman,steve}_resource_*` engine does not already reach.

Reference points: MCP's own client guidance puts tool definitions at 1-5% of a
model's context window. The sibling Arda server runs ~134 tokens/tool.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from rancher_mcp.config import get_settings
from rancher_mcp.server import register_all_tools

# ---------------------------------------------------------------------------
# Budgets. Lower freely; raise only deliberately, with justification.
# ---------------------------------------------------------------------------

MAX_TOTAL_BYTES = 800_000
"""Whole `tools/list` payload. Baseline 2026-08-22: 800,548 B."""

MAX_MEAN_BYTES_PER_TOOL = 2_600
"""Mean per-tool cost. Baseline 2026-08-22: 2,493 B (~605 tokens)."""

MAX_SINGLE_TOOL_BYTES = 7_000
"""No single tool should dominate. Baseline worst: 6,266 B (cluster_get)."""

HOST_INSTRUCTIONS_BUDGET_BYTES = 2_000
"""Claude Code truncates server `instructions` past roughly this."""


def _build() -> FastMCP:
    """Build the real production registry.

    Deliberately self-contained rather than importing the parity gate's
    `build_registered_server` helper: this file is edited in different commits
    than that one, and a shared helper would couple two independent gates.
    """

    mcp = FastMCP(name="footprint-probe")
    register_all_tools(mcp)
    return mcp


def _wire_shape(tool: object) -> dict[str, object]:
    """Exactly the fields `tools/list` puts on the wire for one tool."""

    blob: dict[str, object] = {
        "name": tool.name,  # type: ignore[attr-defined]
        "description": tool.description or "",  # type: ignore[attr-defined]
        "inputSchema": tool.parameters,  # type: ignore[attr-defined]
    }
    output_schema = getattr(tool, "output_schema", None)
    if output_schema:
        blob["outputSchema"] = output_schema
    annotations = getattr(tool, "annotations", None)
    if annotations is not None:
        blob["annotations"] = annotations.model_dump(exclude_none=True)
    title = getattr(tool, "title", None)
    if title:
        blob["title"] = title
    return blob


def _compact(obj: object) -> int:
    return len(json.dumps(obj, separators=(",", ":")))


def _report(blobs: dict[str, dict[str, object]], total: int) -> str:
    """Actionable failure output: where the bytes are and what to look at."""

    fields: dict[str, int] = {}
    for blob in blobs.values():
        for key, value in blob.items():
            fields[key] = fields.get(key, 0) + (
                len(value) if isinstance(value, str) else _compact(value)
            )
    lines = [
        f"tools={len(blobs)}  total={total:,} B ({total / 1024:.1f} KB, ~{total // 4:,} tokens)",
        "by field:",
    ]
    lines += [
        f"    {k:14} {v:>9,} B  {100 * v / total:5.1f}%"
        for k, v in sorted(fields.items(), key=lambda kv: -kv[1])
    ]
    heaviest = sorted(((_compact(b), k) for k, b in blobs.items()), reverse=True)[:5]
    lines.append("heaviest tools:")
    lines += [f"    {size:>7,} B  {name}" for size, name in heaviest]
    return "\n".join(lines)


def test_tools_list_payload_stays_within_budget() -> None:
    mcp = _build()
    tools = mcp._tool_manager.list_tools()
    blobs = {t.name: _wire_shape(t) for t in tools}
    total = _compact({"tools": list(blobs.values())})

    assert total <= MAX_TOTAL_BYTES, (
        f"tools/list payload grew past its budget "
        f"({total:,} B > {MAX_TOTAL_BYTES:,} B).\n"
        f"{_report(blobs, total)}\n"
        "Every byte here is charged to the client's context before it does any work. "
        "Ask whether the new surface tells a model something the generic "
        "rancher_{norman,steve}_resource_* engine does not already reach; if not, it "
        "does not earn a curated tool. Raise the budget only with justification."
    )


def test_mean_cost_per_tool_stays_within_budget() -> None:
    """Guards the OTHER axis. Total bytes can be held flat by deleting tools
    while each surviving tool quietly gets fatter, which is how a surface rots
    without tripping a total-size check."""

    mcp = _build()
    tools = mcp._tool_manager.list_tools()
    mean = sum(_compact(_wire_shape(t)) for t in tools) // len(tools)

    assert mean <= MAX_MEAN_BYTES_PER_TOOL, (
        f"mean per-tool cost grew to {mean:,} B (budget {MAX_MEAN_BYTES_PER_TOOL:,} B, "
        f"~{mean // 4} tokens/tool). The usual cause is an output schema carrying a "
        "deep $defs tree the model never needed to decide whether to CALL the tool."
    )


def test_no_single_tool_dominates() -> None:
    mcp = _build()
    offenders = [
        (t.name, size)
        for t in mcp._tool_manager.list_tools()
        if (size := _compact(_wire_shape(t))) > MAX_SINGLE_TOOL_BYTES
    ]
    assert not offenders, (
        f"tool(s) over the single-tool budget of {MAX_SINGLE_TOOL_BYTES:,} B: "
        f"{sorted(offenders, key=lambda kv: -kv[1])}"
    )


def test_server_instructions_fit_the_host_budget() -> None:
    """`instructions` is the cheapest high-leverage context in the whole server —
    the only place to say what holds ACROSS tools. It should be nearly full and
    must never exceed what the host will actually show."""

    size = len(get_settings().server_instructions.encode())
    assert size <= HOST_INSTRUCTIONS_BUDGET_BYTES, (
        f"server instructions are {size} B, past the ~{HOST_INSTRUCTIONS_BUDGET_BYTES} B "
        "a host will render — the tail would be silently truncated."
    )
    assert size > 800, (
        f"server instructions are only {size} B of a {HOST_INSTRUCTIONS_BUDGET_BYTES} B "
        "budget. This channel is close to free and is the only place to convey "
        "cross-tool structure (the two planes, the generic escape hatch, that "
        "cluster_id defaults to 'local'). Underusing it is a wasted opportunity, "
        "not a safe default."
    )
