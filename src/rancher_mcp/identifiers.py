"""Refuse an identifier that could name something other than what it says.

Identifiers supplied by a caller end up in two places where their exact text
matters: the URL path of a request, and the question a person is asked before
a destructive call. Percent-quoting protects neither.

* A ``..`` segment survives quoting — ``quote("..")`` is ``..`` — and the HTTP
  library resolves it before sending. ``pods/..`` is the namespace;
  ``x/../../clusters/c`` is a different resource altogether.
* A quote or a newline lets the caller write the rest of the sentence the
  person reads, and push the real target off the screen.

This lives below both the client and the service layers because both need it.
The transport has its own last-moment check (``clients/request_guard.py``);
this one runs earlier, so the caller is told which argument was wrong.
"""

from __future__ import annotations

from rancher_mcp.exceptions import RancherInvalidArgumentError

# Characters with no place in a Rancher or Kubernetes identifier, each of which
# can make one mean something else: a quote or a backslash rewrites the prompt
# a person is shown; `#` and `?` end the path early, and `;` separates
# parameters to some servers; `%` smuggles an encoded character past a check
# made on the decoded text.
_FORBIDDEN = frozenset('"\\#?%;')

# The longest name Kubernetes allows (a DNS subdomain); Rancher's own ids are
# far shorter. Anything longer is not a name — it is there to fill a screen.
_LONGEST_NAME = 253


def require_safe_identifier(label: str, value: str, *, single_segment: bool = False) -> str:
    """Return *value* unchanged, or refuse it.

    A ``/`` separates segments (a Steve id is ``namespace/name``; Norman ids
    join with a colon instead), unless ``single_segment`` says the value is one
    name — a schema id, a cluster id, a namespace.
    """

    if not value:
        raise RancherInvalidArgumentError(f"`{label}` must not be empty")
    if any(ch.isspace() or not ch.isprintable() for ch in value):
        raise RancherInvalidArgumentError(
            f"`{label}` contains whitespace or a control character; identifiers have neither"
        )
    forbidden = sorted(_FORBIDDEN.intersection(value))
    if forbidden:
        raise RancherInvalidArgumentError(
            f"`{label}` contains {' '.join(forbidden)} — not valid in an identifier"
        )
    if single_segment and "/" in value:
        raise RancherInvalidArgumentError(f"`{label}` is a single name and cannot contain '/'")
    segments = value.split("/")
    if any(not segment for segment in segments):
        # `/` is the whole collection, not something in it — and a path builder
        # that skipped empty segments once sent a DELETE there.
        raise RancherInvalidArgumentError(
            f"`{label}` has an empty segment — a leading, trailing or doubled '/' — so it "
            "names no one resource"
        )
    if any(segment in {".", ".."} for segment in segments):
        raise RancherInvalidArgumentError(
            f"`{label}` contains a '.' or '..' path segment, which would address a "
            "different resource than the one it names"
        )
    if any(len(segment) > _LONGEST_NAME for segment in segments):
        raise RancherInvalidArgumentError(
            f"`{label}` is longer than any Rancher or Kubernetes name ({_LONGEST_NAME} characters)"
        )
    return value
