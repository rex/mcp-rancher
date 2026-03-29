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
