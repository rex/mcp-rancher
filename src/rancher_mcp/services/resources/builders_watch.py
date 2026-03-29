"""Generic resource watch builders."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.models.resources import GenericResourceWatchEvent, GenericResourceWatchResult
from rancher_mcp.services.resources.builders_item import build_resource_item
from rancher_mcp.services.resources.paths import build_k8s_proxy_resource_path
from rancher_mcp.services.resources.schema import ResourceSchemaReference
from rancher_mcp.services.resources.shared import mapping_value


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
