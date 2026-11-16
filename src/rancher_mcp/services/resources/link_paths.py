"""Request paths taken from a payload's own links.

Rancher tells a client where to go next: every resource carries ``links`` and
``actions`` — full URLs. ``paths.py`` builds a path from identifiers a caller
supplied; this module turns a URL the *server* supplied into one. Two things
are true of everything it returns:

* it is a path on the Rancher this client was configured for — whatever host
  the URL names is dropped, so the path that is checked before sending is the
  path that is sent;
* it is not a WebSocket endpoint. A cluster's ``shell`` link is one: following
  it does not read a document, it starts a session, and Rancher starts that
  by creating a pod.
"""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit

from rancher_mcp.exceptions import RancherCapabilityError, RancherInvalidArgumentError
from rancher_mcp.services.resources.shared import mapping_value

_SESSION_SCHEMES = frozenset({"ws", "wss"})
_SESSION_LINKS = frozenset({"shell", "exec", "attach", "portforward"})


def resolve_resource_action_path(
    *,
    action_name: str,
    payload: Mapping[str, object],
) -> str:
    """Resolve an action path from a resource payload."""

    return _named_path(container_key="actions", entry_name=action_name, payload=payload)


def resolve_resource_link_path(
    *,
    link_name: str,
    payload: Mapping[str, object],
) -> str:
    """Resolve a link path from a resource payload."""

    return _named_path(container_key="links", entry_name=link_name, payload=payload)


def _path_from_value(value: object) -> str | None:
    """Extract a URL path from either a path or fully-qualified URL string."""

    if not isinstance(value, str) or not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return parsed.path or None
    return value


def _normalized_resource_path(
    *,
    plane: str,
    cluster_id: str | None,
    value: object,
) -> str | None:
    """Normalize a self link into a client-usable path."""

    path = _path_from_value(value)
    if path is None:
        return None
    if plane == "steve":
        return _to_steve_relative_path(path, cluster_id)
    return path


def normalize_resource_path(
    *,
    plane: str,
    cluster_id: str | None,
    value: object,
) -> str | None:
    """Normalize a self link into a client-usable path."""

    return _normalized_resource_path(plane=plane, cluster_id=cluster_id, value=value)


def _to_steve_relative_path(path: str, cluster_id: str | None) -> str:
    """Strip the Steve root prefix from a cluster-qualified path."""

    root = "/v1" if cluster_id in {None, "", "local"} else f"/k8s/clusters/{cluster_id}/v1"
    if path == root:
        return "/"
    if path.startswith(f"{root}/"):
        return path[len(root) :]
    return path


def _request_target_from_value(value: object) -> str | None:
    """Extract a request target preserving any query string.

    Only ever a path on the Rancher this client was configured for: whatever
    host a link names is dropped here — named with a scheme or, as
    ``//host/…``, without one — so the path that is checked before sending is
    the path that is sent.
    """

    if not isinstance(value, str) or not value:
        return None
    parsed = urlsplit(value)
    if not parsed.scheme and not parsed.netloc:
        return value
    if parsed.query:
        return f"{parsed.path}?{parsed.query}"
    return parsed.path or None


def _named_path(
    *,
    container_key: str,
    entry_name: str,
    payload: Mapping[str, object],
) -> str:
    """Resolve a named action or link path from a resource payload."""

    container = mapping_value(payload.get(container_key))
    if container is None:
        raise RancherCapabilityError(f"Resource did not include any {container_key}")

    raw_value = container.get(entry_name)
    opens_a_session = entry_name.lower() in _SESSION_LINKS or (
        isinstance(raw_value, str) and urlsplit(raw_value).scheme in _SESSION_SCHEMES
    )
    if opens_a_session:
        # A cluster's `shell` link, for one. Following it with a GET does not
        # read a document: Rancher starts the session by creating a pod. Known
        # by name as well as by scheme, in case a deployment advertises it as
        # plain https.
        raise RancherInvalidArgumentError(
            f"{container_key[:-1]} {entry_name!r} is a WebSocket endpoint: it opens a session "
            "rather than returning a document, and is not followed"
        )
    path = _request_target_from_value(raw_value)
    if path is None:
        raise RancherCapabilityError(
            f"Resource did not include {container_key[:-1]} {entry_name!r}"
        )
    return path


path_from_value = _path_from_value
to_steve_relative_path = _to_steve_relative_path
