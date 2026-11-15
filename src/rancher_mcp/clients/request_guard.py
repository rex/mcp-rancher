"""What may leave the process, checked at the last moment before it does.

Every guard above this layer is a promise made by the code that builds a
request. This is the one place that does not have to trust any of it: both
HTTP clients call :func:`refuse_unsafe_request` immediately before sending.

Three rules.

**A read-only instance sends nothing but reads.** Mutating tools are meant to
refuse a read-only instance themselves, before doing anything, and a
fleet-wide test holds them to it. This is what still holds when one forgets —
as two tools once did, for as long as they existed.

**A request is the method it was sent with.** Rancher lets a query string
overrule the method: ``?_method=DELETE`` on either API plane, and
``?action=remove`` on the management plane, turn a GET into a delete. Every
check in this server — the rule above first of all — judges a request by the
method it chose. So ``_method`` is never sent, and ``action`` only on the POST
that invokes one.

**A request goes where its path says.** A ``.`` or ``..`` segment is resolved
by the HTTP library before the request is sent, so ``…/pods/..`` leaves the
process as the namespace, and ``x/../../clusters/c`` as a different resource
altogether — under whatever confirmation, approval prompt and audit record
described the original. Nothing legitimate needs such a segment, a fragment or
a control character in a path, so none is sent. Nor is a "path" that names a
host. With a scheme (``https://other/…``) the HTTP library sends it there,
carrying this server's token; without one (``//other/…``) it drops the host
and sends a different path from the one that was checked.

See docs/adr/0003-write-guards.md.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import parse_qsl, unquote

import httpx

from rancher_mcp.exceptions import RancherCapabilityError, RancherInvalidArgumentError

# HTTP methods that cannot change anything. Every other method is a mutation.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_DOT_SEGMENTS = frozenset({".", ".."})

# The two query parameters Rancher reads as an instruction about the request
# itself. Both API frameworks take the method from `?_method=` when it is
# there (rancher/norman and rancher/apiserver, `parseMethod`), and Norman turns
# `?action=remove` into a DELETE whatever was sent (`parseAction`).
METHOD_OVERRIDE_PARAM = "_method"
ACTION_PARAM = "action"
REQUEST_REWRITING_PARAMS = frozenset({METHOD_OVERRIDE_PARAM, ACTION_PARAM})


def refuse_unsafe_request(
    *,
    instance_name: str,
    read_only: bool,
    method: str,
    path: str,
    query_keys: Iterable[str] = (),
) -> None:
    """Raise unless this request may be sent as it stands.

    *query_keys* names the query parameters sent alongside *path*; a query
    string inside *path* is read as well.
    """

    verb = method.upper()
    if read_only and verb not in SAFE_METHODS:
        raise RancherCapabilityError(
            f"Rancher instance {instance_name!r} is configured read-only for mutations"
        )

    shown = path if len(path) <= 160 else f"{path[:160]}…"
    if "#" in path or any(not ch.isprintable() for ch in path):
        raise RancherInvalidArgumentError(
            f"Refusing to send {method} {shown!r}: the path contains a fragment or a "
            "control character"
        )
    try:
        parsed = httpx.URL(path)
        names_a_host = bool(parsed.scheme or parsed.host)
    except httpx.InvalidURL:
        names_a_host = True
    if names_a_host:
        raise RancherInvalidArgumentError(
            f"Refusing to send {method} {shown!r}: it names a host, and a request goes only "
            "to the Rancher this instance is configured for"
        )
    target, _, query = path.partition("?")
    keys = {key.strip().lower() for key, _ in parse_qsl(query, keep_blank_values=True)}
    keys.update(key.strip().lower() for key in query_keys)
    if METHOD_OVERRIDE_PARAM in keys:
        raise RancherInvalidArgumentError(
            f"Refusing to send {method} {shown!r}: a `_method` query parameter makes Rancher "
            "act on a different HTTP method than the one sent"
        )
    if ACTION_PARAM in keys and verb != "POST":
        raise RancherInvalidArgumentError(
            f"Refusing to send {method} {shown!r}: an `action` query parameter belongs on the "
            "POST that invokes an action — on anything else Rancher can read it as a delete"
        )
    # Judged after decoding: `%2e%2e` is `..`, and `%2f` is a `/`, to whatever
    # serves the request — so a segment that decodes to either is not one name.
    for segment in target.split("/"):
        decoded = unquote(segment)
        if decoded in _DOT_SEGMENTS:
            raise RancherInvalidArgumentError(
                f"Refusing to send {method} {shown!r}: a '.' or '..' path segment would be "
                "resolved to a different resource than the one named"
            )
        if "/" in decoded or "\\" in decoded:
            raise RancherInvalidArgumentError(
                f"Refusing to send {method} {shown!r}: a path segment contains an encoded "
                "slash, so it names more than one level"
            )
