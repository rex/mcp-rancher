"""Generic Steve watch tools built on Rancher's Kubernetes proxy."""

from __future__ import annotations

from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.clients.streaming import RancherStreamingClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.models.resources import GenericResourceWatchResult
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_watch import build_steve_watch_query_params
from rancher_mcp.services.resources import (
    build_k8s_proxy_collection_path,
    build_resource_watch_result,
    schema_reference_from_payload,
)


async def _watch_steve_resource_collection(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    schema_id: str,
    max_events: int,
    label_selector: str | None,
    field_selector: str | None,
    timeout_seconds: int | None,
    params_json: str | None,
    steve_client: SteveDiscoveryClient,
    streaming_client: RancherStreamingClient,
) -> GenericResourceWatchResult:
    """Watch one Steve resource collection through Rancher's Kubernetes proxy."""

    if max_events < 1:
        raise RancherCapabilityError("max_events must be greater than zero")

    schema_payload = await steve_client.get_json(f"/schemas/{schema_id}")
    schema = schema_reference_from_payload(
        plane="steve",
        cluster_id=cluster_id,
        schema_id=schema_id,
        payload=schema_payload,
    )
    if "watch" not in schema.verbs:
        raise RancherCapabilityError(f"Schema {schema_id!r} does not advertise watch support")

    watch_path = build_k8s_proxy_collection_path(
        schema,
        cluster_id=cluster_id,
        namespace=namespace,
    )
    query_params = build_steve_watch_query_params(
        label_selector=label_selector,
        field_selector=field_selector,
        timeout_seconds=timeout_seconds,
        params_json=params_json,
    )
    capture = await streaming_client.stream_json_lines(
        watch_path,
        params=query_params,
        max_events=max_events,
        idle_timeout_seconds=_watch_idle_timeout_seconds(timeout_seconds),
    )
    return build_resource_watch_result(
        instance=instance_name,
        schema=schema,
        watch_path=watch_path,
        events=capture.events,
        truncated=capture.truncated,
        cluster_id=cluster_id,
        namespace=namespace,
        applied_query_params=query_params,
    )


async def rancher_steve_resource_watch(
    schema_id: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    max_events: int = 20,
    label_selector: str | None = None,
    field_selector: str | None = None,
    timeout_seconds: int | None = 30,
    params_json: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    steve_client: SteveDiscoveryClient | None = None,
    streaming_client: RancherStreamingClient | None = None,
) -> GenericResourceWatchResult:
    """Watch a Steve schema type through Rancher's Kubernetes proxy."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if steve_client is not None and streaming_client is not None:
        return await _watch_steve_resource_collection(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            max_events,
            label_selector,
            field_selector,
            timeout_seconds,
            params_json,
            steve_client,
            streaming_client,
        )

    async with (
        RancherSteveClient(
            instance_name,
            instance_config,
            cluster_id=cluster_id,
        ) as proxy_client,
        RancherStreamingClient(
            instance_name,
            instance_config,
        ) as live_streaming_client,
    ):
        return await _watch_steve_resource_collection(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            max_events,
            label_selector,
            field_selector,
            timeout_seconds,
            params_json,
            proxy_client,
            live_streaming_client,
        )


def _watch_idle_timeout_seconds(timeout_seconds: int | None) -> float:
    """Return a conservative idle timeout for one watch stream."""

    if timeout_seconds is None:
        return 10.0
    return float(max(timeout_seconds + 5, 10))


async def rancher_steve_resource_watch_tool(
    schema_id: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    max_events: int = 20,
    label_selector: str | None = None,
    field_selector: str | None = None,
    timeout_seconds: int | None = 30,
    params_json: str | None = None,
    instance: str | None = None,
) -> GenericResourceWatchResult:
    """Stream change events for a Steve Kubernetes-proxy resource collection up to a
    bounded event count and return them as one batch — the escape hatch for
    watching kinds with no curated tool yet."""

    return await rancher_steve_resource_watch(
        schema_id=schema_id,
        cluster_id=cluster_id,
        namespace=namespace,
        max_events=max_events,
        label_selector=label_selector,
        field_selector=field_selector,
        timeout_seconds=timeout_seconds,
        params_json=params_json,
        instance=instance,
    )
