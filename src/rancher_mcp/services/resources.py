"""Schema-driven generic resource helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast
from urllib.parse import parse_qs, quote, urlsplit

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.models.resources import (
    GenericResourceActionResult,
    GenericResourceDetail,
    GenericResourceItem,
    GenericResourceLinkResult,
    GenericResourceList,
    ResourcePagination,
)


@dataclass(frozen=True)
class ResourceSchemaReference:
    """Internal schema-derived collection metadata."""

    plane: str
    schema_id: str
    plural_name: str
    collection_path: str
    namespaced: bool = False


def parse_payload_object(payload_json: str | None) -> dict[str, object]:
    """Parse a JSON object payload for action invocation."""

    if payload_json is None or not payload_json.strip():
        return {}

    decoded: object = json.loads(payload_json)
    if not isinstance(decoded, dict):
        raise RancherCapabilityError("payload_json must decode to an object")
    return cast(dict[str, object], decoded)


def schema_reference_from_payload(
    *,
    plane: str,
    cluster_id: str | None,
    schema_id: str,
    payload: Mapping[str, object],
) -> ResourceSchemaReference:
    """Build an internal schema reference from a Norman or Steve schema payload."""

    raw_plural_name = payload.get("pluralName")
    if not isinstance(raw_plural_name, str) or not raw_plural_name:
        raise RancherCapabilityError(f"Schema {schema_id!r} did not include a pluralName")

    links = _mapping(payload.get("links"))
    collection_value = links.get("collection") if links is not None else None
    collection_path = _path_from_value(collection_value)

    if collection_path is None:
        collection_path = f"/{raw_plural_name}" if plane == "steve" else f"/v3/{raw_plural_name}"

    if plane == "steve":
        collection_path = _to_steve_relative_path(collection_path, cluster_id)

    attributes = _mapping(payload.get("attributes"))
    raw_namespaced = attributes.get("namespaced") if attributes is not None else None
    namespaced = raw_namespaced is True

    return ResourceSchemaReference(
        plane=plane,
        schema_id=schema_id,
        plural_name=raw_plural_name,
        collection_path=collection_path,
        namespaced=namespaced,
    )


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


def build_resource_list_model(
    *,
    instance: str,
    plane: str,
    schema: ResourceSchemaReference,
    payload: Mapping[str, object],
    cluster_id: str | None = None,
    namespace: str | None = None,
    applied_query_params: Mapping[str, str | int | bool] | None = None,
) -> GenericResourceList:
    """Normalize a collection payload into a generic list model."""

    resources = [
        build_resource_item(
            plane=plane,
            cluster_id=cluster_id,
            payload=item,
        )
        for item in _mapping_list(payload.get("data"))
    ]

    raw_resource_type = payload.get("resourceType")
    resource_type = raw_resource_type if isinstance(raw_resource_type, str) else None

    return GenericResourceList(
        instance=instance,
        plane=plane,
        schema_id=schema.schema_id,
        plural_name=schema.plural_name,
        cluster_id=cluster_id,
        namespace=namespace,
        collection_path=build_collection_path(schema, namespace=namespace),
        resource_count=len(resources),
        resource_type=resource_type,
        collection_action_keys=_mapping_keys(payload.get("actions")),
        collection_link_keys=_mapping_keys(payload.get("links")),
        available_filter_keys=_mapping_keys(payload.get("filters")),
        available_sort_keys=_mapping_keys(payload.get("sort")),
        applied_query_params=dict(applied_query_params or {}),
        pagination=_pagination_from_payload(payload.get("pagination")),
        resources=resources,
    )


def build_resource_detail_model(
    *,
    instance: str,
    plane: str,
    schema: ResourceSchemaReference,
    requested_resource_id: str,
    requested_path: str,
    payload: Mapping[str, object],
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> GenericResourceDetail:
    """Normalize a resource payload into a generic detail model."""

    resource = build_resource_item(
        plane=plane,
        cluster_id=cluster_id,
        payload=payload,
    )
    return GenericResourceDetail(
        instance=instance,
        plane=plane,
        schema_id=schema.schema_id,
        plural_name=schema.plural_name,
        resource_id=resource.id or requested_resource_id,
        cluster_id=cluster_id,
        namespace=resource.namespace or namespace,
        resource_path=resource.resource_path or requested_path,
        type=resource.type,
        action_keys=resource.action_keys,
        link_keys=resource.link_keys,
        payload=resource.payload,
    )


def build_resource_item(
    *,
    plane: str,
    cluster_id: str | None,
    payload: Mapping[str, object],
) -> GenericResourceItem:
    """Normalize one resource object into a generic item model."""

    metadata = _mapping(payload.get("metadata"))
    raw_id = payload.get("id")
    raw_type = payload.get("type")

    if metadata is not None:
        metadata_name = metadata.get("name")
        name = metadata_name if isinstance(metadata_name, str) else None
        metadata_namespace = metadata.get("namespace")
        namespace = metadata_namespace if isinstance(metadata_namespace, str) else None
    else:
        raw_name = payload.get("name")
        name = raw_name if isinstance(raw_name, str) else None
        namespace = None

    links = _mapping(payload.get("links"))
    resource_path = None
    if links is not None:
        resource_path = _normalized_resource_path(
            plane=plane,
            cluster_id=cluster_id,
            value=links.get("self"),
        )

    typed_payload = dict(payload)
    return GenericResourceItem(
        id=raw_id if isinstance(raw_id, str) else None,
        type=raw_type if isinstance(raw_type, str) else None,
        name=name,
        namespace=namespace,
        resource_path=resource_path,
        action_keys=_mapping_keys(payload.get("actions")),
        link_keys=_mapping_keys(payload.get("links")),
        payload=typed_payload,
    )


def resolve_resource_action_path(
    *,
    action_name: str,
    payload: Mapping[str, object],
) -> str:
    """Resolve an action path from a resource payload."""

    return _named_path(
        container_key="actions",
        entry_name=action_name,
        payload=payload,
    )


def resolve_resource_link_path(
    *,
    link_name: str,
    payload: Mapping[str, object],
) -> str:
    """Resolve a link path from a resource payload."""

    return _named_path(
        container_key="links",
        entry_name=link_name,
        payload=payload,
    )


def build_resource_action_result(
    *,
    instance: str,
    plane: str,
    schema_id: str,
    resource_id: str,
    action_name: str,
    action_path: str,
    payload: Mapping[str, object],
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> GenericResourceActionResult:
    """Normalize a resource action response."""

    return GenericResourceActionResult(
        instance=instance,
        plane=plane,
        schema_id=schema_id,
        resource_id=resource_id,
        action_name=action_name,
        cluster_id=cluster_id,
        namespace=namespace,
        action_path=action_path,
        payload=dict(payload),
    )


def build_resource_link_result(
    *,
    instance: str,
    plane: str,
    schema_id: str,
    resource_id: str,
    link_name: str,
    link_path: str,
    payload: Mapping[str, object],
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> GenericResourceLinkResult:
    """Normalize a resource link-follow response."""

    return GenericResourceLinkResult(
        instance=instance,
        plane=plane,
        schema_id=schema_id,
        resource_id=resource_id,
        link_name=link_name,
        cluster_id=cluster_id,
        namespace=namespace,
        link_path=link_path,
        payload=dict(payload),
    )


def _pagination_from_payload(payload: object) -> ResourcePagination | None:
    """Normalize pagination metadata from a collection payload."""

    mapping = _mapping(payload)
    if mapping is None:
        return None

    raw_limit = mapping.get("limit")
    raw_total = mapping.get("total")
    raw_next = mapping.get("next")
    raw_previous = mapping.get("previous")
    raw_continue = mapping.get("continue")
    normalized_next = raw_next if isinstance(raw_next, str) else None
    normalized_previous = raw_previous if isinstance(raw_previous, str) else None
    continue_token = raw_continue if isinstance(raw_continue, str) else None
    if continue_token is None:
        continue_token = _continue_token_from_url(normalized_next)

    return ResourcePagination(
        limit=raw_limit if isinstance(raw_limit, int) else None,
        total=raw_total if isinstance(raw_total, int) else None,
        next=normalized_next,
        previous=normalized_previous,
        continue_token=continue_token,
    )


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


def _path_from_value(value: object) -> str | None:
    """Extract a URL path from either a path or fully-qualified URL string."""

    if not isinstance(value, str) or not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme:
        return parsed.path or None
    return value


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


def _continue_token_from_url(value: str | None) -> str | None:
    """Extract a Kubernetes continue token from a pagination URL."""

    if value is None:
        return None
    parsed = urlsplit(value)
    candidates = parse_qs(parsed.query).get("continue")
    if not candidates:
        return None
    token = candidates[0].strip()
    return token or None


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


def _mapping(payload: object) -> Mapping[str, object] | None:
    """Return a typed mapping if the payload is mapping-like."""

    if not isinstance(payload, Mapping):
        return None
    return cast(Mapping[str, object], payload)


def _mapping_keys(payload: object) -> list[str]:
    """Return sorted keys from a mapping-like payload."""

    mapping = _mapping(payload)
    if mapping is None:
        return []
    return sorted(mapping.keys())


def _mapping_list(payload: object) -> list[Mapping[str, object]]:
    """Return only mapping entries from a list-like payload."""

    if not isinstance(payload, list):
        return []
    items = cast(list[object], payload)
    return [mapping for item in items if (mapping := _mapping(item)) is not None]


def _named_path(
    *,
    container_key: str,
    entry_name: str,
    payload: Mapping[str, object],
) -> str:
    """Resolve a named action or link path from a resource payload."""

    container = _mapping(payload.get(container_key))
    if container is None:
        raise RancherCapabilityError(f"Resource did not include any {container_key}")

    raw_value = container.get(entry_name)
    path = _request_target_from_value(raw_value)
    if path is None:
        raise RancherCapabilityError(
            f"Resource did not include {container_key[:-1]} {entry_name!r}"
        )
    return path
