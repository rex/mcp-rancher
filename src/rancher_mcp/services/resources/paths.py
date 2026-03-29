# pyright: reportUnusedFunction=false
"""Relative path helpers for generic Rancher resources."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.services.resources.shared import mapping_value

if TYPE_CHECKING:
    from rancher_mcp.services.resources.schema import ResourceSchemaReference


def build_collection_path(
    reference: ResourceSchemaReference,
    *,
    namespace: str | None = None,
) -> str:
    """Build a relative collection path for a schema reference."""

    if namespace and reference.namespaced and reference.plane == "steve":
        return _append_identifier(reference.collection_path, namespace)
    return reference.collection_path


def build_resource_path(
    reference: ResourceSchemaReference,
    *,
    resource_id: str,
    namespace: str | None = None,
) -> str:
    """Build a relative resource path for a schema reference."""

    if namespace and reference.namespaced and "/" not in resource_id:
        collection_path = build_collection_path(reference, namespace=namespace)
        return _append_identifier(collection_path, resource_id)
    return _append_identifier(reference.collection_path, resource_id)


def build_k8s_proxy_collection_path(
    reference: ResourceSchemaReference,
    *,
    cluster_id: str,
    namespace: str | None = None,
) -> str:
    """Build a Rancher Kubernetes-proxy collection path from a Steve schema reference."""

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
    if parsed.scheme:
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


def _append_identifier(base_path: str, resource_id: str) -> str:
    """Append a potentially multi-segment resource identifier to a collection path."""

    trimmed = base_path.rstrip("/")
    encoded_segments = [quote(segment, safe="") for segment in resource_id.split("/") if segment]
    if not encoded_segments:
        return trimmed
    return f"{trimmed}/{'/'.join(encoded_segments)}"


def _request_target_from_value(value: object) -> str | None:
    """Extract a request target preserving any query string."""

    if not isinstance(value, str) or not value:
        return None
    parsed = urlsplit(value)
    if not parsed.scheme:
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
    path = _request_target_from_value(raw_value)
    if path is None:
        raise RancherCapabilityError(
            f"Resource did not include {container_key[:-1]} {entry_name!r}"
        )
    return path
