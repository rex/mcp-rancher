"""Fleet-wide gate: no tool may return a body its own published schema rejects.

**The incident this gates.** Thirty-two list tools — pods, deployments,
services, secrets, config maps, events, PVCs and the rest of the namespaced
family — returned a body that violated the ``outputSchema`` the server had
published for them, whenever ``namespace`` was omitted. That is the
cluster-wide list, which the server's own instructions call "usually what
triage wants". The schema listed ``namespace`` as required; the response
envelope drops every null and empty value; so the key was demanded and absent.

Under mcp 1.x the *server* validated its own result and discarded it: the call
came back ``isError``, ``Output validation error: 'namespace' is a required
property``. Under mcp 2.x the server stopped checking and the *client* rejects
it instead. Either way the tool had done its work and the caller got nothing.

**Why it went unseen for months.** The error reads like an input complaint, so
an agent concludes it must pass a namespace, does, and carries on one namespace
at a time. And nothing here exercised it: unit tests call implementations
directly, the live probes call ``mcp.call_tool()`` and so skip validation, and
the older parity gate only ever built a *maximally populated* example — in
which nothing is empty, so nothing is dropped.

**What this file asks instead**, of every registered tool:

1. Build a real body in three shapes — full, sparse and bare (see
   ``_output_contract_support``) — and validate each against the schema the
   tool actually *publishes*, with the validator a client uses.
2. Call every read tool through the request path against a backend with
   nothing in it, and require that the client accepts what comes back. This is
   the check that would have caught the incident outright; the first is what
   makes its failures specific.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from _output_contract_support import SHAPES, build_body, violations
from _output_schema_dump_parity_support import build_registered_server
from _write_guards_support import observe_call, synthesize_arguments

from rancher_mcp import rate_limit
from rancher_mcp.config import clear_settings_cache
from rancher_mcp.schema_compaction import compact_output_schema
from rancher_mcp.sdk_registry import registered_tools

_SERVER = build_registered_server()
_TOOLS = {tool.name: tool for tool in registered_tools(_SERVER)}
_WITH_SCHEMA = sorted(
    name
    for name, tool in _TOOLS.items()
    if tool.output_schema is not None and tool.fn_metadata.output_model is not None
)
_READERS = sorted(
    name
    for name, tool in _TOOLS.items()
    if tool.annotations is not None and tool.annotations.read_only_hint is True
)


@pytest.fixture
def read_only_instance(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("RANCHER_READ_ONLY", "true")
    clear_settings_cache()
    rate_limit.reset_rate_limit_state()
    yield
    clear_settings_cache()
    rate_limit.reset_rate_limit_state()


def test_the_gate_has_real_targets() -> None:
    assert len(_WITH_SCHEMA) == len(_TOOLS) > 100, (
        f"{len(_TOOLS) - len(_WITH_SCHEMA)} of {len(_TOOLS)} tools publish no output schema"
    )
    assert "rancher_pods_list" in _WITH_SCHEMA


@pytest.mark.parametrize("tool_name", _WITH_SCHEMA)
def test_every_shape_of_body_satisfies_the_published_schema(tool_name: str) -> None:
    tool = _TOOLS[tool_name]
    model = tool.fn_metadata.output_model
    published = tool.output_schema
    assert model is not None and published is not None

    problems: list[str] = []
    for shape in SHAPES:
        body = build_body(model, shape)
        problems += [f"[{shape}] {problem}" for problem in violations(published, body)[:4]]

    assert not problems, (
        f"{tool_name} can return a body that its own published outputSchema rejects:\n  - "
        + "\n  - ".join(problems)
        + "\n\nA client that validates results (the SDK's does) fails the whole call. The "
        "envelope drops null and empty values, so a property that can be null, an empty "
        "list or an empty object must not be `required` in what is published — see "
        "`rancher_mcp.schema_compaction`."
    )


@pytest.mark.usefixtures("read_only_instance")
async def test_a_client_accepts_every_read_tool_against_an_empty_backend() -> None:
    """The request-path version: a real client, a backend with nothing in it."""

    rejected: list[str] = []
    for tool_name in _READERS:
        seen = await observe_call(
            _SERVER, tool_name, synthesize_arguments(_TOOLS[tool_name].parameters)
        )
        if seen.rejected_by_client is not None:
            rejected.append(f"{tool_name}: {seen.rejected_by_client[:200]}")

    assert not rejected, (
        f"a validating client rejected the result of {len(rejected)} read tool(s) called with "
        "only their required arguments:\n  " + "\n  ".join(rejected)
    )


def test_the_gate_catches_a_schema_that_demands_a_droppable_key() -> None:
    """Non-vacuity: the incident's exact shape must fail the judge.

    Uses the pods list — a real model from the affected family — against its
    schema *before* the publishing pass has made ``required`` truthful.
    """

    model = _TOOLS["rancher_pods_list"].fn_metadata.output_model
    assert model is not None
    raw = model.model_json_schema(mode="validation")
    assert "namespace" in raw["required"], "the model no longer declares namespace as required"

    found = violations(raw, build_body(model, "bare"))

    assert any("'namespace' is a required property" in problem for problem in found), found
    assert not violations(compact_output_schema(raw), build_body(model, "bare"))
