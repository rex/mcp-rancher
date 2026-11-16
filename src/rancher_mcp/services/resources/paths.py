"""Request paths built from identifiers a caller supplied.

Everything here ends in ``require_safe_identifier``: a path is only ever
assembled from names that have been checked, each quoted into one segment.
Paths taken from a payload's own links are ``link_paths.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.identifiers import require_safe_identifier

if TYPE_CHECKING:
    from rancher_mcp.services.resources.schema import ResourceSchemaReference


def build_collection_path(
    reference: ResourceSchemaReference,
    *,
    namespace: str | None = None,
) -> str:
    """Build a relative collection path for a schema reference."""

    if namespace and reference.namespaced and reference.plane == "steve":
        return _append_identifier(
            reference.collection_path, namespace, label="namespace", single_segment=True
        )
    return reference.collection_path


def build_resource_path(
    reference: ResourceSchemaReference,
    *,
    resource_id: str,
    namespace: str | None = None,
) -> str:
    """Build a relative resource path for a schema reference.

    A management-plane id is one name (its parts are joined with ``:``); only
    a Kubernetes id may be ``namespace/name``. A second segment on the
    management plane is a *link* of the resource, which is not what an id is.
    """

    if namespace and reference.namespaced and "/" not in resource_id:
        collection_path = build_collection_path(reference, namespace=namespace)
        return _append_identifier(collection_path, resource_id)
    return _append_identifier(
        reference.collection_path, resource_id, single_segment=reference.plane == "norman"
    )


def build_k8s_proxy_collection_path(
    reference: ResourceSchemaReference,
    *,
    cluster_id: str,
    namespace: str | None = None,
) -> str:
    """Build a Rancher Kubernetes-proxy collection path from a Steve schema reference."""

    require_safe_identifier("cluster_id", cluster_id, single_segment=True)
    if namespace:
        require_safe_identifier("namespace", namespace, single_segment=True)
    if reference.plane != "steve":
        raise RancherCapabilityError(
            "Kubernetes proxy watch paths are only available for Steve schemas"
        )
    if reference.api_version is None or reference.api_resource is None:
        raise RancherCapabilityError(
            "Schema "
            f"{reference.schema_id!r} did not expose Kubernetes API "
            "group/version/resource metadata"
        )

    if reference.api_group:
        base_path = (
            f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/"
            f"{quote(reference.api_group, safe='')}/{quote(reference.api_version, safe='')}"
        )
    else:
        base_path = (
            f"/k8s/clusters/{quote(cluster_id, safe='')}/api/"
            f"{quote(reference.api_version, safe='')}"
        )

    if namespace and reference.namespaced:
        return (
            f"{base_path}/namespaces/{quote(namespace, safe='')}/"
            f"{quote(reference.api_resource, safe='')}"
        )
    return f"{base_path}/{quote(reference.api_resource, safe='')}"


def build_k8s_proxy_resource_path(
    reference: ResourceSchemaReference,
    *,
    cluster_id: str,
    resource_id: str,
    namespace: str | None = None,
) -> str:
    """Build a Rancher Kubernetes-proxy resource path from a Steve schema reference."""

    return _append_identifier(
        build_k8s_proxy_collection_path(
            reference,
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        resource_id,
    )


def schema_path(root: str, schema_id: str) -> str:
    """The path of one schema under *root* (``/v3/schemas`` or ``/schemas``).

    A schema id is a single name. It used to be interpolated as it came, so a
    ``/``, a ``..`` or a ``#`` in it addressed something else.
    """

    require_safe_identifier("schema_id", schema_id, single_segment=True)
    return f"{root}/{quote(schema_id, safe='')}"


def identified_path(template: str, **identifiers: str) -> str:
    """Fill a path template's ``{placeholders}``, each with one plain name.

    For paths that are written out in full — ``/v3/globalroles/{global_role_id}``,
    ``/pods/{namespace}/{name}``. They used to be f-strings: an id went in as
    it came, so a ``/`` in it reached a link of the resource and a ``?`` added
    query parameters. Each placeholder takes one identifier, refused under the
    name of the argument it came from if it is anything else. ``:`` is left as
    it is, so the path of every valid Norman id is the one always sent.
    """

    filled = {
        name: quote(require_safe_identifier(name, value, single_segment=True), safe=":")
        for name, value in identifiers.items()
    }
    return template.format(**filled)


def _append_identifier(
    base_path: str,
    identifier: str,
    *,
    label: str = "resource_id",
    single_segment: bool = False,
) -> str:
    """Append an identifier — a name, or ``namespace/name`` — to a collection path.

    Quoting each segment is not enough on its own: ``quote("..")`` is ``..``,
    and the HTTP library resolves dot segments before it sends. Nor may any
    segment be empty: skipping empty ones, as this once did, turned the id
    ``/`` into the collection path itself — and a delete of it into a delete
    of everything in the collection. The identifier is refused first, so what
    is returned always names something *under* ``base_path``.
    """

    require_safe_identifier(label, identifier, single_segment=single_segment)
    encoded = "/".join(quote(segment, safe="") for segment in identifier.split("/"))
    return f"{base_path.rstrip('/')}/{encoded}"
