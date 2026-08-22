"""No tool may publish its internal dependency-injection parameters.

Every tool implementation in this repo takes `settings` / `client` / `catalog`
as an injection seam for tests, and is meant to be registered through a thin
`*_tool` wrapper that omits them. Three discovery tools predated that convention
and were registered against their implementations directly, so FastMCP derived
their input schemas from the DI signature and published those parameters as
ordinary, model-callable arguments.

Two consequences, both verified against the running server before the fix:

1. **A caller could override server configuration.** Passing a `settings` object
   to `rancher_instance_list` was honoured: the response came back carrying a
   caller-supplied Rancher URL and `readOnly: false`. The token was never echoed
   (the redaction layer held) and all three tools are read-only, so this was not
   credential exfiltration or a write path — but an agent would believe a
   fabricated instance it had just been handed, which is a model-deception
   vector reachable by prompt injection.
2. **We advertised our own secret env-var names** — `RANCHER_TOKEN`,
   `RANCHER_URL`, `RANCHER_CA_BUNDLE`, `RANCHER_READ_ONLY` — to every client,
   because `AppSettings` was inlined into the published schema. That also cost
   14.7 KB of context across three tools, for parameters no caller should set.

The failure was silent in both directions: nothing validated input schemas, and
the tools worked fine, so it survived a full read-surface capture sweep that was
looking at responses rather than at what we were asking for.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from rancher_mcp.server import register_all_tools

# Constructor-injected collaborators. None of these is ever a caller's business:
# they are process-wide configuration or an already-authenticated HTTP client.
PLUMBING_PARAMETERS = frozenset({"settings", "client", "clients", "catalog", "discovery_client"})

# Types that must never appear in a published schema's `$defs`, because their
# field names describe our deployment rather than Rancher's domain.
INTERNAL_TYPES = frozenset({"AppSettings", "RancherInstanceConfig"})


def _registry() -> FastMCP:
    mcp = FastMCP(name="plumbing-probe")
    register_all_tools(mcp)
    return mcp


def test_no_tool_exposes_internal_plumbing() -> None:
    offenders: list[str] = []
    for tool in _registry()._tool_manager.list_tools():
        leaked = PLUMBING_PARAMETERS & set(tool.parameters.get("properties", {}))
        if leaked:
            offenders.append(f"{tool.name} exposes {sorted(leaked)}")

    assert not offenders, (
        "tool(s) publish internal dependency-injection parameters as callable "
        f"arguments: {offenders}. Register the `*_tool` wrapper rather than the "
        "implementation — the wrapper exists precisely to keep these off the wire."
    )


def test_no_tool_schema_embeds_internal_config_types() -> None:
    """Catches the same defect one level down: a parameter typed as an internal
    model inlines that model's field names into `$defs`, which is how our
    environment-variable names reached every client."""

    offenders: list[str] = []
    for tool in _registry()._tool_manager.list_tools():
        embedded = INTERNAL_TYPES & set(tool.parameters.get("$defs", {}))
        if embedded:
            offenders.append(f"{tool.name} inlines {sorted(embedded)}")

    assert not offenders, (
        f"tool schema(s) embed internal configuration types: {offenders}. "
        "Their field names describe our deployment, not Rancher's domain, and "
        "publishing them tells every client what our secrets are called."
    )


def test_secret_bearing_setting_names_are_absent_from_every_schema() -> None:
    """The blunt backstop. Independent of HOW a leak happens, these strings must
    not appear anywhere in a published input schema."""

    forbidden = ("RANCHER_TOKEN", "RANCHER_CA_BUNDLE", "RANCHER_READ_ONLY")
    offenders: list[str] = []
    for tool in _registry()._tool_manager.list_tools():
        serialized = json.dumps(tool.parameters)
        hits = [needle for needle in forbidden if needle in serialized]
        if hits:
            offenders.append(f"{tool.name}: {hits}")

    assert not offenders, f"published input schema(s) name our secret settings: {offenders}"
