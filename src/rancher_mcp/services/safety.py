"""Shared write-safety helpers for mutation-capable tools."""

from __future__ import annotations

from rancher_mcp.exceptions import RancherCapabilityError
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
