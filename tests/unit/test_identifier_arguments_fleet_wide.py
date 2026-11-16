"""Fleet-wide gate: no argument of any tool can add to the request it names.

**The gap this gates.** Thirty-six curated tools built their path with an
f-string: ``f"/v3/globalroles/{global_role_id}"``. The id went into the URL
exactly as the caller sent it, so ``admin/somelink`` reached a link of the
resource and ``admin?x=1`` added a query parameter — to a server that reads
some query parameters as instructions. The transport refuses the worst of
those, but only the ones it knows about. Found by a second independent review
on 2026-11-15.

**Why nothing noticed.** Every gate before this one synthesized well-formed
arguments from the schema. Hostile ones were tried only against the handful of
generic tools somebody had thought to worry about.

**What this does instead.** For every registered tool, and every string
argument it takes, one at a time, the argument is given a value that tries an
escape — and what is examined is every request target *as it went on the
wire*:

* ``zzA/zzESC`` must not arrive as two path segments;
* ``zzA?zzKEY=1`` and ``zzA;zzKEY=1`` must not arrive as a parameter.

Refusing the call, or sending the value quoted into one segment, both pass. A
tool added tomorrow is covered the moment it is registered.

An *empty* identifier, and ``/``, are a third escape — they turn a resource
path into its collection. Those are not looked for here, because nothing
could be seen: the transport refuses every such request before it is sent
(``test_single_resource_integrity.py``), and a check that sits above a
backstop passes whatever the layer above it does.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

import pytest
from _observing_support import observing
from _output_schema_dump_parity_support import build_registered_server
from _plausible_arguments_support import plausible_arguments
from _write_guards_support import Observation, observe_call
from mcp.server.mcpserver import MCPServer

from rancher_mcp import rate_limit
from rancher_mcp.clients.management import RancherManagementClient
from rancher_mcp.config import clear_settings_cache, clear_toolset_settings_cache, get_settings
from rancher_mcp.sdk_registry import registered_tools
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.support.annotations import READ_ONLY

_SERVER = build_registered_server()
_TOOLS = {tool.name: tool for tool in registered_tools(_SERVER)}
_PROBES = ("zzA/zzESC", "zzA?zzKEY=1", "zzA;zzKEY=1")

# Arguments that are never part of a URL, each for a reason that is checked
# elsewhere: `instance` picks one of the operator's configured instances and an
# unknown one is refused outright (asserted below); `confirmation` is compared
# with a phrase; the JSON-text arguments have their own gates.
_NOT_IDENTIFIERS = frozenset({"instance", "confirmation"})


def _takes_text(schema: dict[str, Any]) -> bool:
    if "enum" in schema:
        return False
    kinds = [schema.get("type"), *(option.get("type") for option in schema.get("anyOf", []))]
    return "string" in kinds


_TARGETS = sorted(
    (name, argument)
    for name, tool in _TOOLS.items()
    for argument, schema in tool.parameters.get("properties", {}).items()
    if _takes_text(schema) and argument not in _NOT_IDENTIFIERS and not argument.endswith("_json")
)


def _reset() -> None:
    clear_settings_cache()
    clear_toolset_settings_cache()
    rate_limit.reset_rate_limit_state()


@pytest.fixture(autouse=True)
def _writable_instance(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("RANCHER_READ_ONLY", "false")
    monkeypatch.setenv("RANCHER_MCP_WRITE_RATE_LIMIT_PER_MIN", "0")
    _reset()
    yield
    _reset()


def escapes(seen: Observation, argument: str) -> list[str]:
    """Every way a request in *seen* carries more than the argument named."""

    found: list[str] = []
    for target in seen.targets:
        path, _, query = target.partition("?")
        # A Kubernetes id is legitimately `namespace/name`.
        if "/zzA/zzESC" in path and argument != "resource_id":
            found.append(f"a second path segment — {target}")
        if "zzKEY=1" in query or ";zzKEY=1" in path:
            found.append(f"a parameter — {target}")
    return found


def test_the_gate_has_real_targets() -> None:
    """Canary: a broken registry would leave the loop below with nothing to do."""

    assert len(_TARGETS) >= 400, len(_TARGETS)
    for expected in [
        ("rancher_global_role_get", "global_role_id"),
        ("rancher_cluster_get", "cluster_id"),
        ("rancher_pod_get", "pod_name"),
        ("rancher_resource_delete", "name"),
        ("rancher_steve_resource_delete", "resource_id"),
    ]:
        assert expected in _TARGETS, expected


async def test_no_argument_of_any_tool_adds_to_the_request() -> None:
    offenders: list[str] = []
    sent = 0
    async with observing(_SERVER) as call:
        for tool_name, argument in _TARGETS:
            for probe in _PROBES:
                arguments = plausible_arguments(tool_name, _TOOLS[tool_name].parameters)
                arguments[argument] = probe

                seen = await call(tool_name, arguments)

                sent += bool(seen.requests)
                offenders.extend(
                    f"{tool_name}({argument}={probe!r}): {escape}"
                    for escape in escapes(seen, argument)
                )

    assert not offenders, (
        f"{len(offenders)} request(s) carried more than the argument named:\n  "
        + "\n  ".join(offenders[:40])
        + "\n\nBuild the path with `identified_path` or `build_resource_path` "
        "(rancher_mcp.services.resources.paths), which validate and quote each identifier."
    )
    assert sent >= len(_TARGETS), (
        f"only {sent} of {len(_TARGETS) * len(_PROBES)} probes got as far as sending anything, "
        "so this is not looking at much — the plausible arguments have stopped working"
    )


@pytest.mark.parametrize("probe", _PROBES)
async def test_an_unknown_instance_is_refused_before_anything_is_sent(probe: str) -> None:
    """Why `instance` is not probed above: it is never part of a URL."""

    seen = await observe_call(
        _SERVER, "rancher_cluster_get", {"cluster_id": "c-1", "instance": probe}
    )

    assert seen.requests == [], seen.requests
    assert seen.is_error, seen.envelope


@pytest.mark.parametrize(
    ("probe", "expected"),
    [
        ("zzA/zzESC", "a second path segment"),
        ("zzA?zzKEY=1", "a parameter"),
        ("zzA;zzKEY=1", "a parameter"),
    ],
)
async def test_the_gate_catches_a_tool_that_interpolates(probe: str, expected: str) -> None:
    """Non-vacuity: the original defect, planted, is seen for each escape."""

    mcp = MCPServer(name="interpolation-probe", instructions="probe")

    @mcp.tool(name="rancher_interpolating_get", annotations=READ_ONLY)
    async def rancher_interpolating_get(thing_id: str) -> str:  # pyright: ignore[reportUnusedFunction]
        instance_name, instance_config = resolve_instance(get_settings(), None)
        async with RancherManagementClient(instance_name, instance_config) as client:
            await client.get_json(f"/v3/things/{thing_id}")
        return "done"

    seen = await observe_call(mcp, "rancher_interpolating_get", {"thing_id": probe})

    assert any(expected in escape for escape in escapes(seen, "thing_id")), seen.targets


async def test_the_gate_reads_what_went_on_the_wire() -> None:
    """Non-vacuity for the other verdict: a value quoted into one segment
    must NOT be taken for an escape, or every careful tool would be an
    offender and the list would mean nothing."""

    mcp = MCPServer(name="quoting-probe", instructions="probe")

    @mcp.tool(name="rancher_quoting_get", annotations=READ_ONLY)
    async def rancher_quoting_get(thing_id: str) -> str:  # pyright: ignore[reportUnusedFunction]
        instance_name, instance_config = resolve_instance(get_settings(), None)
        async with RancherManagementClient(instance_name, instance_config) as client:
            await client.get_json(f"/v3/things/{quote(thing_id, safe='')}")
        return "done"

    seen = await observe_call(mcp, "rancher_quoting_get", {"thing_id": "zzA?zzKEY=1"})

    assert seen.targets == ["/v3/things/zzA%3FzzKEY%3D1"], seen.targets
    assert escapes(seen, "thing_id") == []
