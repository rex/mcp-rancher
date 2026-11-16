"""Machinery for the fleet-wide write-guard gates.

Everything here observes a tool the way a client does: called through the
SDK's in-process client, so the request really travels the server's dispatch
path and every pass ``register_all_tools`` installed. Two things are recorded
that no assertion on a return value can see:

* every HTTP request that left the process (``respx`` intercepts all of them,
  so nothing here can reach a real Rancher), and
* every audit record emitted while the call ran.

Arguments are synthesized from the tool's own published input schema, so a new
tool needs no entry anywhere to be covered.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, cast

import anyio
import httpx
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ElicitRequestParams, ElicitResult, TextContent
from structlog.testing import capture_logs

_CALL_DEADLINE_SECONDS = 20.0

# Enough structure for a tool to keep going after a GET: a collection, an
# object with an id, and an `actions` link for the generic action tools.
_PLAUSIBLE_PAYLOAD: dict[str, object] = {
    "id": "x",
    "type": "x",
    "pluralName": "xs",
    "data": [],
    "items": [],
    "links": {"self": "https://rancher.test.invalid/v3/xs/x"},
    "actions": {"x": "https://rancher.test.invalid/v3/xs/x?action=x"},
    # A workload whose rollout is already over, so a tool that WAITS for one
    # (`rancher_rollout_wait`) returns at once instead of sitting on its timeout.
    "metadata": {"name": "x", "generation": 1},
    "spec": {"replicas": 1},
    "status": {
        "replicas": 1,
        "updatedReplicas": 1,
        "readyReplicas": 1,
        "availableReplicas": 1,
        "observedGeneration": 1,
    },
    "resourceMethods": ["GET", "PUT", "PATCH", "DELETE"],
    "collectionMethods": ["GET", "POST"],
    # What a Steve schema says about its Kubernetes resource. Without it the
    # Steve write and watch tools stop at "schema does not advertise…", and a
    # gate about the request they build would be looking at nothing.
    "attributes": {
        "group": "apps",
        "version": "v1",
        "resource": "xs",
        "kind": "X",
        "namespaced": False,
        "verbs": ["get", "list", "watch", "create", "update", "patch", "delete"],
    },
}


def synthesize_value(schema: dict[str, Any], name: str = "") -> object:
    """The simplest value *schema* accepts."""

    if "enum" in schema:
        return cast(list[object], schema["enum"])[0]
    if "anyOf" in schema:
        for option in cast(list[dict[str, Any]], schema["anyOf"]):
            if option.get("type") != "null":
                return synthesize_value(option, name)
        return None
    kind = schema.get("type")
    if kind == "string":
        return "{}" if name.endswith("_json") else "x"
    if kind in ("integer", "number"):
        return 1
    if kind == "boolean":
        return True
    if kind == "array":
        return []
    if kind == "object":
        return {"k": "v"}
    return "x"


def synthesize_arguments(input_schema: dict[str, Any]) -> dict[str, object]:
    """Required arguments only — what a caller cannot leave out."""

    properties = cast(dict[str, dict[str, Any]], input_schema.get("properties", {}))
    required = cast(list[str], input_schema.get("required", []))
    return {name: synthesize_value(properties[name], name) for name in required}


@dataclass(frozen=True)
class Observation:
    """What one tool call did, as seen from outside the tool."""

    is_error: bool
    envelope: dict[str, Any] | None
    requests: list[str] = field(default_factory=list[str])
    audit: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    rejected_by_client: str | None = None
    """Why the client refused the result, when it did — the body did not match
    the tool's published ``outputSchema``. The tool itself ran to completion."""
    questions: list[str] = field(default_factory=list[str])
    """Every prompt the server put to the person behind the client."""
    query_keys: list[str] = field(default_factory=list[str])
    """The name of every query parameter any request carried."""
    targets: list[str] = field(default_factory=list[str])
    """Every request target exactly as it went on the wire: path and query,
    still percent-encoded. ``requests`` holds the decoded path, in which a
    quoted ``%2F`` and a real ``/`` look the same."""

    @property
    def error_code(self) -> str | None:
        return None if self.envelope is None else cast(str | None, self.envelope.get("error_code"))

    @property
    def message(self) -> str:
        return "" if self.envelope is None else str(self.envelope.get("message", ""))


@dataclass(frozen=True)
class Answer:
    """How the person behind the client responds when the server asks.

    Passing one makes the client declare elicitation; leaving it out gives a
    client that cannot be asked anything, which is most of them.
    """

    action: Literal["accept", "decline", "cancel"]
    proceed: bool | None = None
    keep_going: bool | None = None
    """The second box, where a form has one: "and don't ask again for a while"."""

    def content(self) -> dict[str, str | int | float | bool | list[str] | None] | None:
        """The form as this person filled it in, or nothing if they did not."""

        if self.action != "accept" or self.proceed is None:
            return None
        boxes: dict[str, str | int | float | bool | list[str] | None] = {"proceed": self.proceed}
        if self.keep_going is not None:
            boxes["keep_going"] = self.keep_going
        return boxes


async def observe_call(
    mcp: MCPServer,
    tool_name: str,
    arguments: dict[str, object],
    *,
    answer: Answer | None = None,
    mode: str = "2026-07-28",
) -> Observation:
    """Call *tool_name* through the request path and record what it did."""

    questions: list[str] = []

    async def respond(context: object, params: ElicitRequestParams) -> ElicitResult:
        assert answer is not None
        questions.append(params.message)
        return ElicitResult(action=answer.action, content=answer.content())

    result = None
    rejected_by_client: str | None = None
    with respx.mock(assert_all_called=False) as router, capture_logs() as logs:
        router.route().mock(return_value=httpx.Response(200, json=_PLAUSIBLE_PAYLOAD))
        try:
            async with Client(
                mcp, mode=mode, elicitation_callback=respond if answer is not None else None
            ) as client:
                # A gate must fail, not hang: a tool that waits on something
                # the fake backend never delivers would otherwise stall CI for
                # as long as its own timeout.
                with anyio.fail_after(_CALL_DEADLINE_SECONDS):
                    result = await client.call_tool(tool_name, arguments)
        except TimeoutError as exc:
            raise AssertionError(
                f"{tool_name} did not return within {_CALL_DEADLINE_SECONDS:g}s through the "
                "request path. A tool that waits needs a fake backend that lets it finish "
                "(see _PLAUSIBLE_PAYLOAD)."
            ) from exc
        except Exception as exc:
            # The client validates a result against the tool's published
            # outputSchema and raises when it does not conform. That is a real
            # defect, but a different one from anything observed here: by then
            # the tool has run, and what it sent and logged is still on record.
            rejected_by_client = innermost_message(exc)
        sent = [call.request for call in router.calls]
    return observation_of(result, sent, logs, rejected_by_client, questions)


def observation_of(
    result: CallToolResult | None,
    sent: list[httpx.Request],
    logs: list[Any],
    rejected_by_client: str | None,
    questions: list[str],
) -> Observation:
    """Put together what one call did, from what was collected while it ran."""

    envelope: dict[str, Any] | None = None
    is_error = result is not None and bool(result.is_error)
    if result is not None and is_error and result.content:
        first = result.content[0]
        if isinstance(first, TextContent):
            try:
                parsed: object = json.loads(first.text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                envelope = cast(dict[str, Any], parsed)

    return Observation(
        is_error=is_error,
        envelope=envelope,
        requests=[f"{request.method} {request.url.path}" for request in sent],
        audit=[dict(record) for record in logs if record.get("event") == "audit"],
        rejected_by_client=rejected_by_client,
        questions=list(questions),
        query_keys=sorted({key for request in sent for key in request.url.params}),
        targets=[request.url.raw_path.decode() for request in sent],
    )


def innermost_message(exc: BaseException) -> str:
    """The first leaf of an exception group, as text."""

    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return f"{type(exc).__name__}: {exc}"
