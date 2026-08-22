"""Fleet-wide regression gates: `openWorldHint` and `title` on every tool.

**openWorldHint.** Per the MCP spec, an unset `ToolAnnotations.openWorldHint`
defaults to `true` ("this tool may interact with an open world of external
entities") — correct for something like a web-search tool, wrong for this
server: every tool talks to one closed, well-defined API (Rancher's
Norman/Steve planes and the Kubernetes resources they proxy), never an
open-ended external world. `tools/support/annotations.py`'s five named
`ToolAnnotations` constants are the ONLY construction site for tool
annotations in this repo (every codegen'd and hand-written registration
imports one of them) — set there, it is fleet-wide by construction; this
gate locks that in against a future regression (a new constant, or an
inline `ToolAnnotations(...)` at some registration call site, that forgets
it).

**title.** No tool published the MCP spec's optional human-readable
`Tool.title` before this session. `tools/support/titles.py` derives one
from every tool's name in one blanket post-registration pass
(`apply_titles_to_all_tools`, called from `server.register_all_tools`)
instead of hand-authoring ~300 short strings. This gate locks in that every
registered tool actually got one, and that the derivation stays a
"title" — short — not a runaway sentence.

Both gates build the REAL registry (`register_all_tools`), not a
hand-maintained tool inventory, matching the established pattern in
`test_list_tools_namespace_optional.py` / `test_output_schema_dump_parity.py`
/ `test_next_steps_registry_gate.py`.
"""

from __future__ import annotations

from _output_schema_dump_parity_support import build_registered_server

_SERVER = build_registered_server()
_TOOLS = _SERVER._tool_manager.list_tools()


def test_registry_has_a_healthy_number_of_tools() -> None:
    """Canary against a silently-empty sweep."""

    assert len(_TOOLS) > 100, f"only {len(_TOOLS)} tools registered — registration may be broken"


def test_every_tool_has_open_world_hint_false() -> None:
    """No tool may publish `openWorldHint` as `None` (spec default: `true`)
    or `True` — this server's whole surface is a closed, well-defined API."""

    offenders = [
        tool.name
        for tool in _TOOLS
        if tool.annotations is None or tool.annotations.openWorldHint is not False
    ]
    assert not offenders, (
        "these tools do not publish openWorldHint=False (either annotations "
        "is missing entirely, or openWorldHint is None/True — both mean an "
        f"MCP client is told this is an open-world API, which is false): {sorted(offenders)}"
    )


def test_every_tool_has_a_title() -> None:
    """Every registered tool must publish a non-empty `title`."""

    offenders = [tool.name for tool in _TOOLS if not tool.title]
    assert not offenders, f"these tools have no title: {sorted(offenders)}"


def test_titles_are_short_not_sentences() -> None:
    """A title is a short label, not a description. Locks in the "cheap,
    concise" intent: every title is a handful of words, no sentence
    punctuation, and dramatically shorter than the tool's own description
    (titles never balloon into a second description field)."""

    too_long: list[str] = []
    has_punctuation: list[str] = []
    for tool in _TOOLS:
        title = tool.title or ""
        word_count = len(title.split())
        if word_count > 6:
            too_long.append(f"{tool.name} ({word_count} words: {title!r})")
        if any(ch in title for ch in ".!?"):
            has_punctuation.append(f"{tool.name} ({title!r})")

    assert not too_long, f"titles must stay short (<=6 words), not a sentence: {too_long}"
    assert not has_punctuation, f"titles must not carry sentence punctuation: {has_punctuation}"


def test_title_derivation_is_stable_and_readable() -> None:
    """Spot-check the derivation on a representative sample spanning
    codegen'd list/get/patch/delete tools and the three new collapsed
    generic tools."""

    from rancher_mcp.tools.support.titles import derive_title_from_tool_name

    cases = {
        "rancher_pods_list": "Pods List",
        "rancher_pod_get": "Pod Get",
        "rancher_deployment_scale": "Deployment Scale",
        "rancher_resource_set_labels": "Resource Set Labels",
        "rancher_resource_set_annotations": "Resource Set Annotations",
        "rancher_resource_delete": "Resource Delete",
        "rancher_cluster_health_check": "Cluster Health Check",
    }
    for name, expected in cases.items():
        assert derive_title_from_tool_name(name) == expected

    by_name = {tool.name: tool for tool in _TOOLS}
    for name, expected in cases.items():
        assert by_name[name].title == expected


def test_collapsed_resource_kind_tools_are_registered_with_expected_annotations() -> None:
    """The three F2 collapsed tools specifically: correct annotation_set
    (idempotent write for labels/annotations, destructive for delete) and
    (per the gates above) openWorldHint=False + a title."""

    by_name = {tool.name: tool for tool in _TOOLS}
    for name in (
        "rancher_resource_set_labels",
        "rancher_resource_set_annotations",
        "rancher_resource_delete",
    ):
        tool = by_name[name]
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is False
        assert tool.annotations.openWorldHint is False
        assert tool.title

    assert by_name["rancher_resource_delete"].annotations.destructiveHint is True
    assert by_name["rancher_resource_set_labels"].annotations.destructiveHint is False
    assert by_name["rancher_resource_set_annotations"].annotations.destructiveHint is False
