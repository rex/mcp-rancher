"""Human-readable `title` derivation, applied fleet-wide post-registration.

No tool set the MCP spec's optional `Tool.title` (distinct from
`ToolAnnotations.title` — this is the top-level field FastMCP's
`mcp.tool(title=...)` populates, read fresh from the tool registry by
`FastMCP.list_tools()`). Rather than hand-author ~300 short strings across
every codegen'd descriptor and every hand-written registration call site,
one mechanical derivation from the already-unique, already-descriptive
tool `name` covers all of them, consistently, with no risk of a newly
added tool going untitled.

Deliberately NOT reordered into "Verb Noun" (e.g. "List Pods" instead of
"Pods List"): tool names encode their operation as a SUFFIX
(`rancher_pods_list`, `rancher_pod_get`) for the five codegen operations
but as an arbitrary trailing multi-word verb phrase for hand-authored
patch verbs (`rancher_deployment_set_min_max`,
`rancher_cron_job_suspend`) — detecting "where the verb phrase starts" in
the latter case generically, without a hardcoded verb table that would
need updating for every new patch verb, isn't reliable. Titling each
underscore-separated word in its existing order is simple, deterministic,
and reads fine as a compact UI label even when not perfect verb-first
English (mirrors how many host UIs already show inconsistently-ordered
tool/action labels).
"""

from __future__ import annotations

from typing import Any

from rancher_mcp.sdk_registry import registered_tools

# Tokens that read better upper-cased than title-cased. Small and
# opportunistic — covers the initialisms actually present in this
# server's tool names; not an exhaustive gazetteer.
_ACRONYMS: dict[str, str] = {
    "cis": "CIS",
    "api": "API",
    "id": "ID",
    "url": "URL",
    "tls": "TLS",
    "ca": "CA",
    "crd": "CRD",
    "rbac": "RBAC",
    "cidr": "CIDR",
}


def derive_title_from_tool_name(tool_name: str) -> str:
    """A short, human-readable title derived from a registered tool name.

    ``rancher_pods_list`` -> ``"Pods List"``; ``rancher_pod_get`` ->
    ``"Pod Get"``; ``rancher_resource_set_labels`` -> ``"Resource Set
    Labels"``. Every tool in this server is prefixed ``rancher_`` (dropped
    here — redundant on every single title) and built from
    underscore-separated words, so this never falls back to the raw name.
    """

    stem = tool_name.removeprefix("rancher_")
    words = stem.split("_")
    titled = [_ACRONYMS.get(word, word.capitalize()) for word in words if word]
    return " ".join(titled)


def apply_titles_to_all_tools(mcp: Any) -> None:
    """Set `.title` on every registered tool that doesn't already have one.

    Call once at server construction time, after every pack's
    `register_*_tools` has run (mirrors `apply_metrics_to_all_tools` /
    `apply_structured_errors_to_all_tools` — a blanket post-registration
    pass over the registered tools, rather than threading a `title=` kwarg
    through ~300 individual `mcp.tool(...)` call sites across codegen and
    every hand-written pack). `FastMCP.list_tools()` reads `Tool.title`
    fresh at request time, so mutating it here after the fact is enough.
    """

    for tool in registered_tools(mcp):
        if tool.title is None:
            tool.title = derive_title_from_tool_name(tool.name)
