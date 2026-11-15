"""Arguments that get a tool as far as building its request.

``synthesize_arguments`` gives the minimum a schema accepts, which is what a
gate about *refusals* wants: a read-only instance or an empty rate-limit
bucket turns the call away before its arguments matter. A gate about the
request a tool **builds** needs the call to get that far — and the minimum
does not: an empty payload and a wrong confirmation phrase are each refused
first, and a call refused for that says nothing about anything after it.
"""

from __future__ import annotations

from typing import Any

from _write_guards_support import synthesize_arguments


def plausible_arguments(tool_name: str, input_schema: dict[str, Any]) -> dict[str, object]:
    """The synthesized minimum, with the two values that are checked early
    replaced by ones that pass."""

    arguments = synthesize_arguments(input_schema)
    if "payload_json" in arguments:
        arguments["payload_json"] = '{"metadata": {"name": "x"}}'
    if "confirmation" in arguments:
        plane = "norman" if "_norman_" in tool_name else "steve"
        arguments["confirmation"] = f"delete {plane} x x"
    return arguments
