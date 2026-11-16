"""What a refusal has to look like, for the fleet-wide write-guard gates.

A tool that turns a call away has four things to get right: it sends nothing,
it reports an error, the error says *why*, and it leaves a record that
somebody tried. Each function here lists every one a call got wrong.
"""

from __future__ import annotations

from _write_guards_support import Observation


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
