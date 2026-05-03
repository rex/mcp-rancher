"""Kubernetes event listing tool."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.ops.events import RancherEventList, RancherEventSummary
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.ops.paths import k8s_core_ns_path, k8s_items
from rancher_mcp.tools.support.values import mapping_value, string_value


def _int_or_none(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _event_summary(item: dict[str, object], namespace: str) -> RancherEventSummary:
    metadata = mapping_value(item, "metadata") or {}
    involved = mapping_value(item, "involvedObject") or {}
    return RancherEventSummary(
        name=string_value(metadata, "name") or "<unknown-event>",
        namespace=string_value(metadata, "namespace") or namespace,
        reason=string_value(item, "reason"),
        message=string_value(item, "message"),
        event_type=string_value(item, "type"),
        count=_int_or_none(item.get("count")),
        involved_kind=string_value(involved, "kind"),
        involved_name=string_value(involved, "name"),
        first_timestamp=string_value(item, "firstTimestamp"),
        last_timestamp=string_value(item, "lastTimestamp"),
    )


async def _fetch_cluster_events_list(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    event_type: str | None,
    reason: str | None,
    client: ManagementDiscoveryClient,
) -> RancherEventList:
    ns = namespace or "default"
    path = k8s_core_ns_path(cluster_id, ns, "events")
    payload = await client.get_json(path)
    events = [_event_summary(item, ns) for item in k8s_items(payload)]

    if event_type is not None:
        events = [e for e in events if e.event_type == event_type]
    if reason is not None:
        events = [e for e in events if e.reason == reason]

    return RancherEventList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        event_count=len(events),
        events=events,
    )


async def rancher_cluster_events_list(
    cluster_id: str = "local",
    namespace: str | None = None,
    event_type: str | None = None,
    reason: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherEventList:
    """List Kubernetes events in a namespace, optionally filtered by type or reason."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_cluster_events_list(
            instance_name, cluster_id, namespace, event_type, reason, client
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_cluster_events_list(
            instance_name, cluster_id, namespace, event_type, reason, managed_client
        )


async def rancher_cluster_events_list_tool(
    cluster_id: str = "local",
    namespace: str | None = None,
    event_type: str | None = None,
    reason: str | None = None,
    instance: str | None = None,
) -> RancherEventList:
    """List Kubernetes events in a namespace. Filter by event_type (Warning/Normal) or reason."""

    return await rancher_cluster_events_list(
        cluster_id=cluster_id,
        namespace=namespace,
        event_type=event_type,
        reason=reason,
        instance=instance,
    )
