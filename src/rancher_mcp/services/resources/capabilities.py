"""Capability and payload helpers for generic resource mutations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.services.resources.schema import ResourceSchemaReference


def ensure_create_supported(reference: ResourceSchemaReference) -> None:
    """Require collection-level create support for one schema."""

    if "create" in reference.verbs or "POST" in reference.collection_methods:
        return
    raise RancherCapabilityError(
        f"Schema {reference.schema_id!r} does not advertise create support"
    )


def ensure_apply_supported(reference: ResourceSchemaReference) -> None:
    """Require apply/update support for one schema on the active API plane."""

    if reference.plane == "norman":
        if "update" in reference.verbs or "PUT" in reference.resource_methods:
            return
        raise RancherCapabilityError(
            f"Schema {reference.schema_id!r} does not advertise update support for Norman apply"
        )

    if "patch" in reference.verbs or "PATCH" in reference.resource_methods:
        return
    raise RancherCapabilityError(
        f"Schema {reference.schema_id!r} does not advertise patch support for Steve apply"
    )


def ensure_patch_supported(reference: ResourceSchemaReference) -> None:
    """Require patch support for one schema on the active API plane."""

    if reference.plane == "norman":
        if "update" in reference.verbs or "PUT" in reference.resource_methods:
            return
        raise RancherCapabilityError(
            f"Schema {reference.schema_id!r} does not advertise update support for Norman patch"
        )

    if "patch" in reference.verbs or "PATCH" in reference.resource_methods:
        return
    raise RancherCapabilityError(f"Schema {reference.schema_id!r} does not advertise patch support")


def ensure_delete_supported(reference: ResourceSchemaReference) -> None:
    """Require delete support for one schema."""

    if "delete" in reference.verbs or "DELETE" in reference.resource_methods:
        return
    raise RancherCapabilityError(
        f"Schema {reference.schema_id!r} does not advertise delete support"
    )


def restrict_payload_fields(
    payload: Mapping[str, object],
    allowed_fields: frozenset[str],
    *,
    source_name: str = "payload_json",
) -> dict[str, object]:
    """Restrict a payload to fields the schema advertises for the operation."""

    if not allowed_fields:
        return dict(payload)

    invalid_fields = sorted(set(payload).difference(allowed_fields))
    if invalid_fields:
        joined = ", ".join(invalid_fields)
        raise RancherCapabilityError(
            f"{source_name} included fields the schema does not advertise for this operation: "
            f"{joined}"
        )
    return dict(payload)


def merge_patch_object(
    base_payload: Mapping[str, object],
    patch_payload: Mapping[str, object],
) -> dict[str, object]:
    """Recursively merge a patch object into a mutable resource payload."""

    merged = dict(base_payload)
    for key, raw_value in patch_payload.items():
        current_value = merged.get(key)
        if isinstance(raw_value, Mapping) and isinstance(current_value, Mapping):
            merged[key] = merge_patch_object(
                cast(Mapping[str, object], current_value),
                cast(Mapping[str, object], raw_value),
            )
            continue
        merged[key] = cast(object, raw_value)
    return merged
