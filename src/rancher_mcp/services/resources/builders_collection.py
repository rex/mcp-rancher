"""Generic resource list/detail builders."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.resources import GenericResourceDetail, GenericResourceList
from rancher_mcp.services.resources.builders_item import build_resource_item
from rancher_mcp.services.resources.builders_pagination import pagination_from_payload
from rancher_mcp.services.resources.paths import build_collection_path
from rancher_mcp.services.resources.schema import ResourceSchemaReference
from rancher_mcp.services.resources.shared import mapping_keys, mapping_list


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
        pagination=pagination_from_payload(payload.get("pagination")),
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
