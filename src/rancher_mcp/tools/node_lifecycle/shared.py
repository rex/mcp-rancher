"""Shared helpers for Rancher-managed node lifecycle actions (Track E).

Node cordon / uncordon / drain are exposed by Rancher as Norman *actions* on
the ``/v3/nodes`` management resource. These helpers resolve the action URL
from the live node payload's ``actions`` map (never hardcoded) and POST the
action, mirroring the proven generic action-invoke path so the call works
across Rancher versions.
"""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient
from rancher_mcp.models.resources import GenericResourceActionResult
from rancher_mcp.services.resources import (
    build_resource_action_result,
    build_resource_item,
    build_resource_path,
    parse_payload_object,
    resolve_resource_action_path,
    schema_reference_from_payload,
)

NODE_SCHEMA_ID = "node"


async def invoke_node_action(
    *,
    instance_name: str,
    node_id: str,
    action_name: str,
    payload_json: str | None,
    client: ManagementDiscoveryClient,
) -> GenericResourceActionResult:
    """Resolve a Norman node action from the live node payload and POST it.

    ``node_id`` is the Rancher management node id in ``{cluster}:{machine}``
    form (e.g. ``local:m-abc123``). The action URL is read from the node's
    ``actions`` map, so the call does not hardcode endpoints.
    """

    schema_payload = await client.get_json(f"/v3/schemas/{NODE_SCHEMA_ID}")
    schema = schema_reference_from_payload(
        plane="norman",
        cluster_id=None,
        schema_id=NODE_SCHEMA_ID,
        payload=schema_payload,
    )
    resource_path = build_resource_path(schema, resource_id=node_id)
    resource_payload = await client.get_json(resource_path)
    action_path = resolve_resource_action_path(
        action_name=action_name,
        payload=resource_payload,
    )
    response_payload = await client.post_json(
        action_path,
        payload=parse_payload_object(payload_json),
    )
    resource = build_resource_item(
        plane="norman",
        cluster_id=None,
        payload=resource_payload,
    )
    return build_resource_action_result(
        instance=instance_name,
        plane="norman",
        schema_id=NODE_SCHEMA_ID,
        resource_id=resource.id or node_id,
        action_name=action_name,
        action_path=action_path,
        payload=response_payload,
    )
