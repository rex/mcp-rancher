"""Shared write-safety helpers for mutation-capable tools."""

from __future__ import annotations

from rancher_mcp.exceptions import RancherCapabilityError, RancherInvalidArgumentError
from rancher_mcp.models.discovery import RancherInstanceConfig


def ensure_instance_writable(
    instance_name: str,
    instance_config: RancherInstanceConfig,
) -> None:
    """Reject write operations against read-only instance configurations."""

    if instance_config.read_only:
        raise RancherCapabilityError(
            f"Rancher instance {instance_name!r} is configured read-only for mutations"
        )


def require_consistent_namespace(namespace: str | None, resource_id: str) -> None:
    """Refuse a ``namespace`` that disagrees with the one in ``resource_id``.

    A Steve id of the form ``namespace/name`` already says where the resource
    lives, and that is the namespace the request uses. A second, different
    ``namespace`` argument is ignored by the request — so it can only ever
    mislead whoever reads the call, the prompt or the audit record.
    """

    if namespace is None or "/" not in resource_id:
        return
    named = resource_id.split("/", 1)[0]
    if named != namespace:
        raise RancherInvalidArgumentError(
            f"`namespace` is {namespace!r} but `resource_id` names namespace {named!r}; "
            "pass one, or make them agree"
        )


def delete_confirmation_phrase(
    *,
    plane: str,
    schema_id: str,
    resource_id: str,
) -> str:
    """Return the exact confirmation phrase required for one generic delete."""

    return f"delete {plane} {schema_id} {resource_id}"


def require_delete_confirmation(
    *,
    plane: str,
    schema_id: str,
    resource_id: str,
    confirmation: str,
) -> str:
    """Require an explicit confirmation phrase for destructive deletes."""

    expected = delete_confirmation_phrase(
        plane=plane,
        schema_id=schema_id,
        resource_id=resource_id,
    )
    if confirmation != expected:
        raise RancherCapabilityError(
            f"Delete confirmation did not match the required phrase: {expected}"
        )
    return expected
