"""What may leave the process, checked at the last moment before it does.

Every guard above this layer is a promise made by the code that builds a
request. This is the one place that does not have to trust any of it: both
HTTP clients call :func:`refuse_unsafe_request` immediately before sending.

Four rules.

**A read-only instance sends nothing but reads.** Mutating tools are meant to
refuse a read-only instance themselves, before doing anything, and a
fleet-wide test holds them to it. This is what still holds when one forgets —
as two tools once did, for as long as they existed.

**A request is the method it was sent with.** Rancher lets a query string
overrule the method: ``?_method=DELETE`` on either API plane, and
``?action=remove`` on the management plane, turn a GET into a delete. Every
check in this server — the rule above first of all — judges a request by the
method it chose. So ``_method`` is never sent, and ``action`` only on the POST
that invokes one. Nor is ``shell``: a GET carrying it creates a pod.

**A request goes where its path says.** A ``.`` or ``..`` segment is resolved
by the HTTP library before the request is sent, so ``…/pods/..`` leaves the
process as the namespace, and ``x/../../clusters/c`` as a different resource
altogether — under whatever confirmation, approval prompt and audit record
described the original. Nothing legitimate needs such a segment, a fragment or
a control character in a path, so none is sent. Nor is a "path" that names a
host. With a scheme (``https://other/…``) the HTTP library sends it there,
carrying this server's token; without one (``//other/…``) it drops the host
and sends a different path from the one that was checked.

**A change is made to one resource.** A path with an empty segment, or a
mutation on a path that ends in ``/``, names a collection or nothing at all —
which is what an empty or ``/`` identifier turns a resource path into. And a
``DELETE`` on a Kubernetes collection path is *deletecollection*: everything
of that kind, in the namespace or the cluster. It is never sent.

See docs/adr/0003-write-guards.md.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import unquote, unquote_plus

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
# `?shell=true` on a cluster is a kubectl shell. Rancher creates the pod it
# runs in before it looks at anything else about the request, so even a GET
# that goes on to fail has written to the cluster.
SHELL_PARAM = "shell"
REQUEST_REWRITING_PARAMS = frozenset({METHOD_OVERRIDE_PARAM, ACTION_PARAM, SHELL_PARAM})


# What follows the API root of a Kubernetes path, through Rancher's proxy or
# not: `…/api/v1/<rest>` or `…/apis/<group>/<version>/<rest>`.
_KUBERNETES_REST = re.compile(r"^(?:/k8s/clusters/[^/]+)?/(?:api/[^/]+|apis/[^/]+/[^/]+)/(.+)$")


def _is_kubernetes_collection(target: str) -> bool:
    """Whether *target* is a Kubernetes collection rather than one object.

    ``<resource>`` and ``namespaces/<ns>/<resource>`` are collections; add a
    name and it is an object. ``namespaces/<ns>`` is an object too — the
    namespace itself.
    """

    match = _KUBERNETES_REST.match(target)
    if match is None:
        return False
    rest = match.group(1).split("/")
    return len(rest) == 1 or (len(rest) == 3 and rest[0] == "namespaces")


def _query_keys(query: str) -> set[str]:
    """Every parameter name in *query*, read as the most permissive server would.

    ``;`` separates as well as ``&``: Go's parser did that before 1.17, and a
    Rancher built with it reads ``?a=1;_method=DELETE`` as two parameters.
    """

    pairs = (pair for pair in re.split("[&;]", query) if pair)
    return {unquote_plus(pair.partition("=")[0]).strip().lower() for pair in pairs}


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
    keys = _query_keys(query)
    keys.update(key.strip().lower() for key in query_keys)
    if METHOD_OVERRIDE_PARAM in keys:
        raise RancherInvalidArgumentError(
            f"Refusing to send {method} {shown!r}: a `_method` query parameter makes Rancher "
            "act on a different HTTP method than the one sent"
        )
    if SHELL_PARAM in keys:
        raise RancherInvalidArgumentError(
            f"Refusing to send {method} {shown!r}: a `shell` query parameter opens a shell "
            "session on a cluster, which starts by creating a pod — whatever the method"
        )
    if ACTION_PARAM in keys and verb != "POST":
        raise RancherInvalidArgumentError(
            f"Refusing to send {method} {shown!r}: an `action` query parameter belongs on the "
            "POST that invokes an action — on anything else Rancher can read it as a delete"
        )
    segments = target.split("/")
    if "" in segments[1:-1]:
        raise RancherInvalidArgumentError(
            f"Refusing to send {method} {shown!r}: an empty path segment (`//`) is collapsed "
            "or reinterpreted by the server, so the request names something else"
        )
    if verb not in SAFE_METHODS and len(target) > 1 and target.endswith("/"):
        raise RancherInvalidArgumentError(
            f"Refusing to send {method} {shown!r}: a path ending in `/` names a collection, "
            "and a change is made to one resource"
        )
    # Judged as the server will route it: `%6Eamespaces` is `namespaces` there.
    if verb == "DELETE" and _is_kubernetes_collection("/".join(map(unquote, segments))):
        raise RancherInvalidArgumentError(
            f"Refusing to send {method} {shown!r}: a DELETE on a Kubernetes collection "
            "deletes everything in it, and this server deletes one resource at a time"
        )
    # Judged after decoding: `%2e%2e` is `..`, and `%2f` is a `/`, to whatever
    # serves the request — so a segment that decodes to either is not one name.
    for segment in segments:
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
