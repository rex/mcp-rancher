"""Find unready or unschedulable nodes."""

from __future__ import annotations

from typing import cast

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.ops.failure_finders import UnreadyNodesList, UnreadyNodeSummary
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.support.conditions import condition_is_true, conditions_from_value
from rancher_mcp.tools.support.values import string_value


async def _find_unready_nodes(
    instance_name: str,
    client: ManagementDiscoveryClient,
    cluster_id: str | None,
) -> UnreadyNodesList:
    """Scan nodes for not-ready or unschedulable state."""

    params: dict[str, str | int | bool] = {}
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    payload = await client.get_json("/v3/nodes", params=params or None)
    raw_data = payload.get("data")
    if not isinstance(raw_data, list):
        return UnreadyNodesList(
            instance=instance_name,
            cluster_id=cluster_id,
            unready_count=0,
        )

    unready: list[UnreadyNodeSummary] = []
    for raw_node in cast(list[object], raw_data):
        if not isinstance(raw_node, dict):
            continue
        node = cast(dict[str, object], raw_node)
        conditions = conditions_from_value(node.get("conditions"))
        ready = condition_is_true(conditions, "Ready")
        is_unschedulable = node.get("unschedulable") is True

        if ready is not True or is_unschedulable:
            ready_cond = next(
                (c for c in conditions if c.type == "Ready"),
                None,
            )
            roles: list[str] = []
            if node.get("controlPlane") is True:
                roles.append("control-plane")
            if node.get("etcd") is True:
                roles.append("etcd")
            if node.get("worker") is True:
                roles.append("worker")

            unready.append(
                UnreadyNodeSummary(
                    id=string_value(node, "id") or "<unknown>",
                    name=string_value(node, "name") or "<unknown>",
                    state=string_value(node, "state"),
                    roles=roles,
                    unschedulable=is_unschedulable,
                    ready_condition_status=(ready_cond.status if ready_cond else None),
                    ready_condition_message=(ready_cond.message if ready_cond else None),
                )
            )

    return UnreadyNodesList(
        instance=instance_name,
        cluster_id=cluster_id,
        unready_count=len(unready),
        nodes=unready,
    )


async def rancher_find_unready_nodes(
    cluster_id: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> UnreadyNodesList:
    """Find nodes that are not ready or unschedulable."""

    resolved = settings or get_settings()
    name, config = resolve_instance(resolved, instance)
    if client is not None:
        return await _find_unready_nodes(name, client, cluster_id)
    async with RancherManagementClient(name, config) as mc:
        return await _find_unready_nodes(name, mc, cluster_id)


async def rancher_find_unready_nodes_tool(
    cluster_id: str | None = None,
    instance: str | None = None,
) -> UnreadyNodesList:
    """Find unready or unschedulable nodes across clusters."""

    return await rancher_find_unready_nodes(
        cluster_id=cluster_id,
        instance=instance,
    )
