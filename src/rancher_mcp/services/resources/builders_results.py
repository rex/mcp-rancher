"""Generic resource action/link result builders."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.resources import GenericResourceActionResult, GenericResourceLinkResult


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
