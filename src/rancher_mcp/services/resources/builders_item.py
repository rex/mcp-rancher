"""Generic resource item normalization."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.resources import GenericResourceItem
from rancher_mcp.services.resources.paths import normalize_resource_path
from rancher_mcp.services.resources.shared import mapping_keys, mapping_value


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
        resource_path = normalize_resource_path(
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
