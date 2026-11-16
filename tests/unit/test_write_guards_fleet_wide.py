"""Fleet-wide gate: every tool that can write obeys the three write guards.

**The incident this gates.** The safety model makes three promises about any
tool that can change something: a read-only instance refuses it, it is counted
against the write rate limit, and it leaves an audit record. Two tools — the
generic ``rancher_{norman,steve}_resource_action_invoke``, which POST an
arbitrary Rancher action — kept none of them, from the day they were written
until 2026-11-15. On an instance marked read-only they went ahead and invoked
the action, uncounted and unrecorded.

**Why nothing noticed.** Each guard was tested per tool, in the test file
written alongside that tool, by whoever wrote the tool. A tool whose author
forgot the guard had a test file that did not ask about it. Nothing asked the
question of the fleet. (See ``docs/adr/0003-write-guards.md``.)

**What this file does instead.** It derives its targets from the same
annotation a client reads — every registered tool *not* marked
``readOnlyHint`` — and calls each one the way a client does, with every HTTP
request intercepted:

* against a read-only instance it must refuse *as* read-only, send nothing at
  all (not even a preliminary GET), and leave an audit record;
* with the write bucket empty it must refuse as rate limited, send nothing,
  and leave an audit record.

The annotation is what the gate trusts, so it is checked from the other side
too: every tool that *is* marked read-only must only ever send ``GET``. A
write tool mislabelled as a read would otherwise walk out of scope unseen.

A tool added tomorrow is covered the moment it is registered.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from _output_schema_dump_parity_support import build_registered_server
from _refusal_problems_support import rate_limit_refusal_problems, read_only_refusal_problems
from _write_guards_support import Observation, observe_call, synthesize_arguments
from mcp.server.mcpserver import MCPServer

from rancher_mcp import rate_limit
from rancher_mcp.clients.management import RancherManagementClient
from rancher_mcp.config import clear_settings_cache, get_settings
from rancher_mcp.sdk_registry import RegisteredTool, registered_tools
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.support.annotations import READ_ONLY, SAFE_WRITE

_SERVER = build_registered_server()


def _is_read_only(tool: RegisteredTool) -> bool:
    return tool.annotations is not None and tool.annotations.read_only_hint is True


_TOOLS = {tool.name: tool for tool in registered_tools(_SERVER)}
_WRITERS = sorted(name for name, tool in _TOOLS.items() if not _is_read_only(tool))
_READERS = sorted(name for name, tool in _TOOLS.items() if _is_read_only(tool))


@pytest.fixture
def read_only_instance(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The one configured instance is read-only for the duration of a test."""

    monkeypatch.setenv("RANCHER_READ_ONLY", "true")
    clear_settings_cache()
    rate_limit.reset_rate_limit_state()
    yield
    clear_settings_cache()
    rate_limit.reset_rate_limit_state()


@pytest.fixture
def writable_instance(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The one configured instance accepts writes, so nothing downstream of a
    tool can be what stopped one."""

    monkeypatch.setenv("RANCHER_READ_ONLY", "false")
    clear_settings_cache()
    rate_limit.reset_rate_limit_state()
    yield
    clear_settings_cache()
    rate_limit.reset_rate_limit_state()


@pytest.fixture
def empty_write_bucket(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A writable instance whose write budget has just been spent."""

    monkeypatch.setenv("RANCHER_READ_ONLY", "false")
    monkeypatch.setenv("RANCHER_MCP_WRITE_RATE_LIMIT_PER_MIN", "1")
    clear_settings_cache()
    rate_limit.reset_rate_limit_state()
    bucket = rate_limit._get_or_build_bucket(get_settings())  # pyright: ignore[reportPrivateUsage]
    assert bucket is not None
    while bucket.try_consume():
        pass
    yield
    clear_settings_cache()
    rate_limit.reset_rate_limit_state()


def test_the_gate_has_real_targets() -> None:
    """Canary: a broken registry would make every parametrized case vanish."""

    assert len(_WRITERS) >= 20, f"only {len(_WRITERS)} write tools found: {_WRITERS}"
    assert len(_READERS) >= 100, f"only {len(_READERS)} read tools found"
    assert "rancher_norman_resource_action_invoke" in _WRITERS
    assert "rancher_steve_resource_action_invoke" in _WRITERS


@pytest.mark.usefixtures("read_only_instance")
@pytest.mark.parametrize("tool_name", _WRITERS)
async def test_a_read_only_instance_refuses_every_tool_that_can_write(tool_name: str) -> None:
    arguments = synthesize_arguments(_TOOLS[tool_name].parameters)

    seen = await observe_call(_SERVER, tool_name, arguments)

    problems = read_only_refusal_problems(seen)
    assert not problems, (
        f"{tool_name} is not annotated read-only, and against a READ-ONLY instance it:\n  - "
        + "\n  - ".join(problems)
        + "\n\nA read-only instance must refuse every mutation before anything is sent. "
        "Call `ensure_instance_writable` first in the implementation, inside "
        "`@audit_mutation` and `@rate_limit_writes` — see docs/adr/0003-write-guards.md."
    )


@pytest.mark.usefixtures("empty_write_bucket")
@pytest.mark.parametrize("tool_name", _WRITERS)
async def test_an_empty_write_bucket_refuses_every_tool_that_can_write(tool_name: str) -> None:
    arguments = synthesize_arguments(_TOOLS[tool_name].parameters)

    seen = await observe_call(_SERVER, tool_name, arguments)

    problems = rate_limit_refusal_problems(seen)
    assert not problems, (
        f"{tool_name} is not annotated read-only, and with the write budget spent it:\n  - "
        + "\n  - ".join(problems)
        + "\n\nEvery mutation counts against the write rate limit. Decorate the "
        "implementation with `@audit_mutation(...)` outside `@rate_limit_writes`."
    )


def _writes(seen: Observation) -> list[str]:
    """Every request in *seen* that was not a read."""

    return [request for request in seen.requests if not request.startswith("GET ")]


@pytest.mark.usefixtures("writable_instance")
async def test_tools_annotated_read_only_only_ever_read() -> None:
    """The other half: the annotation the gates above trust must be true.

    Asked of a WRITABLE instance, and it has to be. On a read-only one the
    transport refuses every write before it is sent, so a write tool mislabelled
    as a read would show nothing here — which is how this check stood, proving
    nothing, from the day that backstop was added until a review noticed.
    """

    offenders: list[str] = []
    reached_http = 0
    for tool_name in _READERS:
        seen = await observe_call(
            _SERVER, tool_name, synthesize_arguments(_TOOLS[tool_name].parameters)
        )
        reached_http += bool(seen.requests)
        writes = _writes(seen)
        if writes:
            offenders.append(f"{tool_name}: {writes}")

    assert not offenders, (
        "these tools are annotated readOnlyHint but sent a request that is not a GET:\n  "
        + "\n  ".join(offenders)
    )
    assert reached_http >= len(_READERS) * 0.8, (
        f"only {reached_http} of {len(_READERS)} read tools got as far as sending a request, "
        "so this check is not looking at much — the synthesized arguments have stopped working"
    )


@pytest.mark.usefixtures("writable_instance")
async def test_the_gate_catches_a_write_mislabelled_as_a_read() -> None:
    """Non-vacuity for the check above: a tool annotated read-only that POSTs
    is seen to. On a read-only instance this very call shows nothing."""

    mcp = MCPServer(name="mislabelled-probe", instructions="probe")

    @mcp.tool(name="rancher_mislabelled_read", annotations=READ_ONLY)
    async def rancher_mislabelled_read(resource_id: str) -> str:  # pyright: ignore[reportUnusedFunction]
        instance_name, instance_config = resolve_instance(get_settings(), None)
        async with RancherManagementClient(instance_name, instance_config) as client:
            await client.post_json(f"/v3/xs/{resource_id}?action=x")
        return "done"

    seen = await observe_call(mcp, "rancher_mislabelled_read", {"resource_id": "x"})

    assert _writes(seen) == ["POST /v3/xs/x"], seen.requests


@pytest.mark.usefixtures("read_only_instance")
async def test_the_gate_catches_a_tool_that_forgot_its_guards() -> None:
    """Non-vacuity: plant the original defect and watch the gate object.

    This is the shape the two action tools had — look the resource up, then
    POST — with no guard, no audit and no rate limit. If the checks above could
    not see that, they would be passing for the wrong reason.
    """

    mcp = MCPServer(name="write-guard-probe", instructions="probe")

    @mcp.tool(name="rancher_forgetful_action", annotations=SAFE_WRITE)
    async def rancher_forgetful_action(resource_id: str) -> str:  # pyright: ignore[reportUnusedFunction]
        instance_name, instance_config = resolve_instance(get_settings(), None)
        async with RancherManagementClient(instance_name, instance_config) as client:
            await client.get_json(f"/v3/xs/{resource_id}")
            await client.post_json(f"/v3/xs/{resource_id}?action=x")
        return "done"

    seen = await observe_call(mcp, "rancher_forgetful_action", {"resource_id": "x"})

    problems = read_only_refusal_problems(seen)
    assert any("sent 1 HTTP request" in problem for problem in problems), problems
    assert any("no audit record" in problem for problem in problems), problems
    # ...and the backstop held anyway: the lookup went out, the write did not.
    assert seen.requests == ["GET /v3/xs/x"], seen.requests
