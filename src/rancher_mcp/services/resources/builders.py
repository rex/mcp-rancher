# pyright: reportPrivateUsage=false
"""Typed model builders for generic Rancher resources."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from urllib.parse import parse_qs, urlsplit

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.models.resources import (
    GenericResourceActionResult,
    GenericResourceDetail,
    GenericResourceItem,
    GenericResourceLinkResult,
    GenericResourceList,
    GenericResourceWatchEvent,
    GenericResourceWatchResult,
    ResourcePagination,
)
from rancher_mcp.services.resources.paths import (
    _normalized_resource_path,
    build_collection_path,
    build_k8s_proxy_resource_path,
)
from rancher_mcp.services.resources.schema import ResourceSchemaReference
from rancher_mcp.services.resources.shared import mapping_keys, mapping_list, mapping_value


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
        build_resource_item(plane=plane, cluster_id=cluster_id, payload=item)
        for item in mapping_list(payload.get("data"))
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
        collection_action_keys=mapping_keys(payload.get("actions")),
        collection_link_keys=mapping_keys(payload.get("links")),
        available_filter_keys=mapping_keys(payload.get("filters")),
        available_sort_keys=mapping_keys(payload.get("sort")),
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

    resource = build_resource_item(plane=plane, cluster_id=cluster_id, payload=payload)
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


def build_resource_watch_result(
    *,
    instance: str,
    schema: ResourceSchemaReference,
    watch_path: str,
    events: Sequence[Mapping[str, object]],
    truncated: bool,
    cluster_id: str,
    namespace: str | None = None,
    applied_query_params: Mapping[str, str | int | bool] | None = None,
) -> GenericResourceWatchResult:
    """Normalize Kubernetes watch events into a generic watch model."""

    normalized_events = [
        build_resource_watch_event(
            schema=schema,
            cluster_id=cluster_id,
            payload=event_payload,
            namespace=namespace,
        )
        for event_payload in events
    ]
    return GenericResourceWatchResult(
        instance=instance,
        plane=schema.plane,
        schema_id=schema.schema_id,
        plural_name=schema.plural_name,
        cluster_id=cluster_id,
        namespace=namespace,
        watch_path=watch_path,
        event_count=len(normalized_events),
        truncated=truncated,
        applied_query_params=dict(applied_query_params or {}),
        events=normalized_events,
    )


def build_resource_watch_event(
    *,
    schema: ResourceSchemaReference,
    cluster_id: str,
    payload: Mapping[str, object],
    namespace: str | None = None,
) -> GenericResourceWatchEvent:
    """Normalize one Kubernetes watch event."""

    raw_event_type = payload.get("type")
    if not isinstance(raw_event_type, str) or not raw_event_type:
        raise RancherCapabilityError("Watch event payload did not include a string type")

    resource_payload = mapping_value(payload.get("object"))
    if resource_payload is None:
        raise RancherCapabilityError("Watch event payload did not include an object resource")

    resource = build_resource_item(
        plane=schema.plane,
        cluster_id=cluster_id,
        payload=resource_payload,
    )
    resource_namespace = resource.namespace or namespace
    resource_id = resource.id
    resource_path = resource.resource_path
    if resource_path is None and resource.name is not None:
        resource_path = build_k8s_proxy_resource_path(
            schema,
            cluster_id=cluster_id,
            namespace=resource_namespace,
            resource_id=resource.name,
        )
    if resource_id is None and resource.name is not None:
        resource_id = (
            f"{resource_namespace}/{resource.name}"
            if resource_namespace is not None
            else resource.name
        )

    return GenericResourceWatchEvent(
        event_type=raw_event_type,
        resource_id=resource_id,
        resource_type=resource.type,
        name=resource.name,
        namespace=resource_namespace,
        resource_path=resource_path,
        payload=dict(resource_payload),
    )


def build_resource_item(
    *,
    plane: str,
    cluster_id: str | None,
    payload: Mapping[str, object],
) -> GenericResourceItem:
    """Normalize one resource object into a generic item model."""

    metadata = mapping_value(payload.get("metadata"))
    raw_id = payload.get("id")
    raw_type = payload.get("type")
    raw_kind = payload.get("kind")

    if metadata is not None:
        metadata_name = metadata.get("name")
        name = metadata_name if isinstance(metadata_name, str) else None
        metadata_namespace = metadata.get("namespace")
        namespace = metadata_namespace if isinstance(metadata_namespace, str) else None
    else:
        raw_name = payload.get("name")
        name = raw_name if isinstance(raw_name, str) else None
        namespace = None

    links = mapping_value(payload.get("links"))
    resource_path = None
    if links is not None:
        resource_path = _normalized_resource_path(
            plane=plane,
            cluster_id=cluster_id,
            value=links.get("self"),
        )

    if isinstance(raw_id, str):
        resource_id = raw_id
    elif name is not None:
        resource_id = f"{namespace}/{name}" if namespace is not None else name
    else:
        resource_id = None

    if isinstance(raw_type, str):
        resource_type = raw_type
    elif isinstance(raw_kind, str) and raw_kind:
        resource_type = raw_kind.lower()
    else:
        resource_type = None

    return GenericResourceItem(
        id=resource_id,
        type=resource_type,
        name=name,
        namespace=namespace,
        resource_path=resource_path,
        action_keys=mapping_keys(payload.get("actions")),
        link_keys=mapping_keys(payload.get("links")),
        payload=dict(payload),
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

    mapping = mapping_value(payload)
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
