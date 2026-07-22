"""Cordon and uncordon a Rancher-managed node.

Both are reversible scheduling toggles (IDEMPOTENT_WRITE): cordon marks a node
unschedulable; uncordon restores scheduling. They invoke the Rancher Norman
``cordon`` / ``uncordon`` node actions. Evicting running pods is the separate
DESTRUCTIVE ``rancher_node_drain`` workflow (follow-up slice).
"""

from __future__ import annotations

from rancher_mcp.audit import audit_mutation
from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceActionResult
from rancher_mcp.rate_limit import rate_limit_writes
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.safety import ensure_instance_writable
from rancher_mcp.tools.node_lifecycle.shared import invoke_node_action


@audit_mutation(operation="cordon", plane="norman")
@rate_limit_writes
async def rancher_node_cordon(
    node_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> GenericResourceActionResult:
    """Mark a Rancher-managed node unschedulable via the `cordon` action.

    Reversible with `rancher_node_uncordon`; does not evict running pods (use
    `rancher_node_drain` for that). `node_id` is the management node id in
    `{cluster}:{machine}` form (e.g. `local:m-abc123`).
    """

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    ensure_instance_writable(instance_name, instance_config)
    if client is not None:
        return await invoke_node_action(
            instance_name=instance_name,
            node_id=node_id,
            action_name="cordon",
            payload_json=None,
            client=client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await invoke_node_action(
            instance_name=instance_name,
            node_id=node_id,
            action_name="cordon",
            payload_json=None,
            client=managed_client,
        )


@audit_mutation(operation="uncordon", plane="norman")
@rate_limit_writes
async def rancher_node_uncordon(
    node_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> GenericResourceActionResult:
    """Restore scheduling to a cordoned node via the `uncordon` action.

    `node_id` is the management node id in `{cluster}:{machine}` form.
    """

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    ensure_instance_writable(instance_name, instance_config)
    if client is not None:
        return await invoke_node_action(
            instance_name=instance_name,
            node_id=node_id,
            action_name="uncordon",
            payload_json=None,
            client=client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await invoke_node_action(
            instance_name=instance_name,
            node_id=node_id,
            action_name="uncordon",
            payload_json=None,
            client=managed_client,
        )


async def rancher_node_cordon_tool(
    node_id: str,
    instance: str | None = None,
) -> GenericResourceActionResult:
    """Mark a Rancher-managed node unschedulable so the scheduler stops placing new
    pods there, without evicting anything already running, and return the action
    result — reversible with `rancher_node_uncordon`."""

    return await rancher_node_cordon(node_id=node_id, instance=instance)


async def rancher_node_uncordon_tool(
    node_id: str,
    instance: str | None = None,
) -> GenericResourceActionResult:
    """Restore scheduling on a previously cordoned Rancher-managed node so the
    scheduler resumes placing new pods there, and return the action result."""

    return await rancher_node_uncordon(node_id=node_id, instance=instance)
