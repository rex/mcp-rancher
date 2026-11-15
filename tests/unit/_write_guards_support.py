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
from typing import Any, cast

import httpx
import respx
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import TextContent
from structlog.testing import capture_logs

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
    "metadata": {"name": "x"},
    "resourceMethods": ["GET", "PUT", "DELETE"],
    "collectionMethods": ["GET", "POST"],
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

    @property
    def error_code(self) -> str | None:
        return None if self.envelope is None else cast(str | None, self.envelope.get("error_code"))

    @property
    def message(self) -> str:
        return "" if self.envelope is None else str(self.envelope.get("message", ""))


async def observe_call(mcp: MCPServer, tool_name: str, arguments: dict[str, object]) -> Observation:
    """Call *tool_name* through the request path and record what it did."""

    result = None
    rejected_by_client: str | None = None
    with respx.mock(assert_all_called=False) as router, capture_logs() as logs:
        router.route().mock(return_value=httpx.Response(200, json=_PLAUSIBLE_PAYLOAD))
        try:
            async with Client(mcp, mode="2026-07-28") as client:
                result = await client.call_tool(tool_name, arguments)
        except Exception as exc:
            # The client validates a result against the tool's published
            # outputSchema and raises when it does not conform. That is a real
            # defect, but a different one from anything observed here: by then
            # the tool has run, and what it sent and logged is still on record.
            rejected_by_client = _innermost_message(exc)
        requests = [f"{call.request.method} {call.request.url.path}" for call in router.calls]

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
        requests=requests,
        audit=[dict(record) for record in logs if record.get("event") == "audit"],
        rejected_by_client=rejected_by_client,
    )


def _innermost_message(exc: BaseException) -> str:
    """The first leaf of an exception group, as text."""

    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return f"{type(exc).__name__}: {exc}"


def read_only_refusal_problems(seen: Observation) -> list[str]:
    """Everything wrong with how a write tool treated a READ-ONLY instance.

    Empty means the tool did what the safety model promises: refused, said
    why, sent nothing, and left a record that somebody tried.
    """

    problems: list[str] = []
    if seen.requests:
        problems.append(f"sent {len(seen.requests)} HTTP request(s): {seen.requests[:4]}")
    if not seen.is_error:
        problems.append("returned success")
    elif seen.error_code != "CAPABILITY_ERROR" or "read-only" not in seen.message:
        problems.append(
            f"refused, but not as a read-only refusal: {seen.error_code!r} {seen.message!r}"
        )
    if not [record for record in seen.audit if record.get("outcome") == "error"]:
        problems.append("left no audit record of the refused attempt")
    return problems


def rate_limit_refusal_problems(seen: Observation) -> list[str]:
    """Everything wrong with how a write tool treated an EMPTY write bucket."""

    problems: list[str] = []
    if seen.requests:
        problems.append(f"sent {len(seen.requests)} HTTP request(s): {seen.requests[:4]}")
    if not seen.is_error:
        problems.append("returned success")
    elif seen.error_code != "RATE_LIMITED":
        problems.append(f"refused, but not as rate limited: {seen.error_code!r} {seen.message!r}")
    if not [record for record in seen.audit if record.get("error_code") == "RATE_LIMITED"]:
        problems.append("left no audit record of the rate-limited attempt")
    return problems
