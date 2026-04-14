"""Generic resource action/link result builders."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.resources import (
    GenericResourceActionResult,
    GenericResourceLinkResult,
    GenericResourceMutationResult,
)
from rancher_mcp.services.resources.builders_item import build_resource_item


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


def build_resource_mutation_result(
    *,
    instance: str,
    plane: str,
    schema_id: str,
    operation: str,
    request_method: str,
    request_path: str,
    payload: Mapping[str, object],
    cluster_id: str | None = None,
    namespace: str | None = None,
    resource_id_hint: str | None = None,
    resource_path_hint: str | None = None,
) -> GenericResourceMutationResult:
    """Normalize a generic create/apply/patch/delete response."""

    resource = build_resource_item(
        plane=plane,
        cluster_id=cluster_id,
        payload=payload,
    )
    return GenericResourceMutationResult(
        instance=instance,
        plane=plane,
        schema_id=schema_id,
        operation=operation,
        request_method=request_method,
        request_path=request_path,
        cluster_id=cluster_id,
        namespace=resource.namespace or namespace,
        resource_id=resource.id or resource_id_hint,
        resource_path=resource.resource_path or resource_path_hint,
        type=resource.type,
        action_keys=resource.action_keys,
        link_keys=resource.link_keys,
        payload=dict(payload),
    )
