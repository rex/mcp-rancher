"""Hints a client reads from a tool's ``_meta`` entry in ``tools/list``.

Keys under ``anthropic/`` belong to Claude Code. They are not part of MCP, and
a client that does not recognise them ignores them — so they cost every other
client a few bytes and nothing else. They are also independent of protocol era:
a ``tools/list`` entry looks the same on the legacy handshake and on
``2026-07-28``, which is why these could ship before the port.

Applied as post-registration data passes, like titles and schema compaction,
rather than threaded through ~200 ``mcp.tool(...)`` call sites across codegen
and the hand-written packs.

Reference: ``docs/reference/claude-code-mcp-client.md`` §3.
"""

from __future__ import annotations

from typing import Any, Final

from rancher_mcp.sdk_registry import registered_tools

ALWAYS_LOAD_META_KEY: Final = "anthropic/alwaysLoad"

#: The front door: the tools that are plausible FIRST calls in a session.
#:
#: With tool search — Claude Code's default — only tool *names* and the server
#: instructions load at session start; every definition sits behind a
#: ``ToolSearch`` round trip. Marking a tool here loads its definition upfront,
#: so the first triage call needs no search. It is the ``core`` profile idea
#: delivered without removing a single tool: a small always-visible entrance,
#: everything else still discoverable.
#:
#: Chosen by measuring, not by taste. Each entry costs context on EVERY turn of
#: every session this server is connected to, including the ones that are not
#: about Rancher at all — so membership is "would the model reach for this
#: before it has learned anything?", and nothing else:
#:
#: * ``clusters_health_summary`` — fleet state, and the cluster ids every other
#:   call needs (``cluster_id`` otherwise defaults to ``local``).
#: * ``cluster_health_check`` — one cluster, in depth.
#: * ``find_failing_pods`` / ``find_unready_nodes`` — what is broken right now.
#: * ``resource_events`` — what happened to one object.
#:
#: Together about 2,360 characters (~590 tokens) of name + description + input
#: schema. ``tests/unit/test_client_hints.py`` budgets the set so it cannot grow
#: by accretion, and requires every member to be read-only.
#:
#: Whoever configures the server keeps the last word: ``"alwaysLoad": false`` on
#: its MCP config entry defers every tool again, marked or not.
ALWAYS_LOAD_TOOLS: Final[frozenset[str]] = frozenset(
    {
        "rancher_clusters_health_summary",
        "rancher_cluster_health_check",
        "rancher_find_failing_pods",
        "rancher_find_unready_nodes",
        "rancher_resource_events",
    }
)


def apply_always_load(mcp: Any) -> None:
    """Mark the front-door tools to load upfront in clients that defer tools.

    Only tools that are actually registered are touched, so a reduced toolset
    profile that drops one of them is not an error — it simply has a smaller
    front door.

    Construction time only, never per request.
    """

    for tool in registered_tools(mcp):
        if tool.name in ALWAYS_LOAD_TOOLS:
            tool.meta = {**(tool.meta or {}), ALWAYS_LOAD_META_KEY: True}
