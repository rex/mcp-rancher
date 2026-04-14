"""Schema reference helpers for generic Rancher resources."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.services.resources.paths import path_from_value, to_steve_relative_path
from rancher_mcp.services.resources.shared import mapping_value


@dataclass(frozen=True)
class ResourceSchemaReference:
    """Internal schema-derived collection metadata."""

    plane: str
    schema_id: str
    plural_name: str
    collection_path: str
    namespaced: bool = False
    api_group: str | None = None
    api_version: str | None = None
    api_resource: str | None = None
    verbs: tuple[str, ...] = ()
    collection_methods: tuple[str, ...] = ()
    resource_methods: tuple[str, ...] = ()
    creatable_fields: frozenset[str] = frozenset()
    updatable_fields: frozenset[str] = frozenset()


def parse_payload_object(payload_json: str | None) -> dict[str, object]:
    """Parse a JSON object payload for action invocation."""

    if payload_json is None or not payload_json.strip():
        return {}

    decoded: object = json.loads(payload_json)
    if not isinstance(decoded, dict):
        raise RancherCapabilityError("payload_json must decode to an object")
    return cast(dict[str, object], decoded)


def parse_required_payload_object(
    payload_json: str | None,
    *,
    source_name: str = "payload_json",
) -> dict[str, object]:
    """Parse a non-empty JSON object payload for mutation requests."""

    payload = parse_payload_object(payload_json)
    if not payload:
        raise RancherCapabilityError(f"{source_name} must decode to a non-empty object")
    return payload


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

    links = mapping_value(payload.get("links"))
    collection_value = links.get("collection") if links is not None else None
    collection_path = path_from_value(collection_value)

    if collection_path is None:
        collection_path = f"/{raw_plural_name}" if plane == "steve" else f"/v3/{raw_plural_name}"

    if plane == "steve":
        collection_path = to_steve_relative_path(collection_path, cluster_id)

    attributes = mapping_value(payload.get("attributes"))
    raw_namespaced = attributes.get("namespaced") if attributes is not None else None
    raw_group = attributes.get("group") if attributes is not None else None
    raw_version = attributes.get("version") if attributes is not None else None
    raw_resource = attributes.get("resource") if attributes is not None else None
    raw_verbs = attributes.get("verbs") if attributes is not None else None
    raw_collection_methods = payload.get("collectionMethods")
    raw_resource_methods = payload.get("resourceMethods")
    resource_fields = mapping_value(payload.get("resourceFields"))

    return ResourceSchemaReference(
        plane=plane,
        schema_id=schema_id,
        plural_name=raw_plural_name,
        collection_path=collection_path,
        namespaced=raw_namespaced is True,
        api_group=raw_group if isinstance(raw_group, str) else None,
        api_version=raw_version if isinstance(raw_version, str) else None,
        api_resource=raw_resource if isinstance(raw_resource, str) else None,
        verbs=_string_tuple(raw_verbs),
        collection_methods=_upper_string_tuple(raw_collection_methods),
        resource_methods=_upper_string_tuple(raw_resource_methods),
        creatable_fields=_field_name_set(resource_fields, key="create"),
        updatable_fields=_field_name_set(resource_fields, key="update"),
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    """Normalize an arbitrary JSON value into a tuple of strings."""

    if not isinstance(value, list):
        return ()
    items: list[str] = []
    for item in cast(list[object], value):
        if isinstance(item, str):
            items.append(item)
    return tuple(items)


def _upper_string_tuple(value: object) -> tuple[str, ...]:
    """Normalize an arbitrary JSON value into an uppercase tuple of strings."""

    if not isinstance(value, list):
        return ()
    items: list[str] = []
    for item in cast(list[object], value):
        if isinstance(item, str):
            items.append(item.upper())
    return tuple(items)


def _field_name_set(
    resource_fields: Mapping[str, object] | None,
    *,
    key: str,
) -> frozenset[str]:
    """Collect top-level field names that advertise one mutation capability."""

    if resource_fields is None:
        return frozenset()

    names = {
        field_name
        for field_name, raw_metadata in resource_fields.items()
        if (metadata := mapping_value(raw_metadata)) is not None and metadata.get(key) is True
    }
    return frozenset(names)
