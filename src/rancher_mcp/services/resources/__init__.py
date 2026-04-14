"""Structured generic resource helpers with stable public exports."""

from rancher_mcp.services.resources.builders import (
    build_resource_action_result,
    build_resource_detail_model,
    build_resource_item,
    build_resource_link_result,
    build_resource_list_model,
    build_resource_mutation_result,
    build_resource_watch_event,
    build_resource_watch_result,
)
from rancher_mcp.services.resources.contexts import (
    ResourceContext,
    load_norman_resource_context,
    load_norman_schema_reference,
    load_steve_resource_context,
    load_steve_schema_reference,
)
from rancher_mcp.services.resources.paths import (
    build_collection_path,
    build_k8s_proxy_collection_path,
    build_k8s_proxy_resource_path,
    build_resource_path,
    resolve_resource_action_path,
    resolve_resource_link_path,
)
from rancher_mcp.services.resources.schema import (
    ResourceSchemaReference,
    parse_payload_object,
    schema_reference_from_payload,
)

__all__ = [
    "ResourceSchemaReference",
    "build_collection_path",
    "build_k8s_proxy_collection_path",
    "build_k8s_proxy_resource_path",
    "build_resource_action_result",
    "build_resource_detail_model",
    "build_resource_item",
    "build_resource_link_result",
    "build_resource_list_model",
    "build_resource_mutation_result",
    "build_resource_path",
    "build_resource_watch_event",
    "build_resource_watch_result",
    "load_norman_resource_context",
    "load_norman_schema_reference",
    "load_steve_resource_context",
    "load_steve_schema_reference",
    "parse_payload_object",
    "ResourceContext",
    "resolve_resource_action_path",
    "resolve_resource_link_path",
    "schema_reference_from_payload",
]
