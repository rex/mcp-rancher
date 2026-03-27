"""Curated Rancher project and namespace read-only tools."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from mcp.server.fastmcp import FastMCP

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.models.projects_namespaces import (
    RancherNamespaceDetail,
    RancherNamespaceList,
    RancherNamespaceSummary,
    RancherProjectDetail,
    RancherProjectList,
    RancherProjectSummary,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import build_steve_list_query_params


async def _fetch_projects_list(
    instance_name: str,
    cluster_id: str | None,
    state: str | None,
    limit: int | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherProjectList:
    """Fetch and normalize the Rancher projects collection."""

    query_params = _build_project_query_params(
        cluster_id=cluster_id,
        state=state,
        limit=limit,
        sort_by=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/projects", params=query_params or None)
    projects = [_project_summary_from_payload(item) for item in _data_items(payload)]
    return RancherProjectList(
        instance=instance_name,
        project_count=len(projects),
        applied_query_params=query_params,
        projects=projects,
    )


async def rancher_projects_list(
    cluster_id: str | None = None,
    state: str | None = None,
    limit: int | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherProjectList:
    """List Rancher projects with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_projects_list(
            instance_name,
            cluster_id,
            state,
            limit,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_projects_list(
            instance_name,
            cluster_id,
            state,
            limit,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_project_get(
    instance_name: str,
    project_id: str,
    client: ManagementDiscoveryClient,
) -> RancherProjectDetail:
    """Fetch and normalize one Rancher project."""

    payload = await client.get_json(f"/v3/projects/{project_id}")
    summary = _project_summary_from_payload(payload)
    return RancherProjectDetail(
        id=summary.id,
        name=summary.name,
        cluster_id=summary.cluster_id,
        state=summary.state,
        description=summary.description,
        monitoring_enabled=summary.monitoring_enabled,
        default_project=summary.default_project,
        system_project=summary.system_project,
        condition_types_true=summary.condition_types_true,
        namespace_id=_string_value(payload, "namespaceId"),
        pod_security_policy_template_id=_string_value(payload, "podSecurityPolicyTemplateId"),
        transitioning=_string_value(payload, "transitioning"),
        transitioning_message=_string_value(payload, "transitioningMessage"),
        action_keys=sorted(_mapping_value(payload, "actions") or {}),
        link_keys=sorted(_mapping_value(payload, "links") or {}),
        conditions=_conditions_from_payload(payload),
        payload=dict(payload),
    )


async def rancher_project_get(
    project_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherProjectDetail:
    """Fetch one Rancher project by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_project_get(instance_name, project_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_project_get(instance_name, project_id, managed_client)


async def _fetch_namespaces_list(
    instance_name: str,
    cluster_id: str,
    phase: str | None,
    project_id: str | None,
    limit: int | None,
    label_selector: str | None,
    field_selector: str | None,
    client: SteveDiscoveryClient,
) -> RancherNamespaceList:
    """Fetch and normalize downstream namespaces."""

    query_params = _build_namespace_query_params(
        project_id=project_id,
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
    )
    payload = await client.get_json("/namespaces", params=query_params or None)
    namespaces = [
        _namespace_summary_from_payload(cluster_id, item) for item in _data_items(payload)
    ]
    if phase is not None:
        namespaces = [namespace for namespace in namespaces if namespace.phase == phase]
    return RancherNamespaceList(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace_count=len(namespaces),
        applied_query_params=query_params,
        namespaces=namespaces,
    )


async def rancher_namespaces_list(
    cluster_id: str = "local",
    phase: str | None = None,
    project_id: str | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> RancherNamespaceList:
    """List downstream namespaces with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_namespaces_list(
            instance_name,
            cluster_id,
            phase,
            project_id,
            limit,
            label_selector,
            field_selector,
            client,
        )
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as steve_client:
        return await _fetch_namespaces_list(
            instance_name,
            cluster_id,
            phase,
            project_id,
            limit,
            label_selector,
            field_selector,
            steve_client,
        )


async def _fetch_namespace_get(
    instance_name: str,
    cluster_id: str,
    namespace: str,
    client: SteveDiscoveryClient,
) -> RancherNamespaceDetail:
    """Fetch and normalize one downstream namespace."""

    payload = await client.get_json(f"/namespaces/{namespace}")
    summary = _namespace_summary_from_payload(cluster_id, payload)
    metadata = _mapping_value(payload, "metadata") or {}
    annotations = _mapping_value(metadata, "annotations") or {}
    labels = _mapping_value(metadata, "labels") or {}
    return RancherNamespaceDetail(
        id=summary.id,
        name=summary.name,
        cluster_id=summary.cluster_id,
        phase=summary.phase,
        state_name=summary.state_name,
        state_message=summary.state_message,
        state_error=summary.state_error,
        project_id=summary.project_id,
        project_id_short=summary.project_id_short,
        finalizer_count=summary.finalizer_count,
        label_keys=sorted(_string_dict(labels)),
        annotation_keys=sorted(_string_dict(annotations)),
        finalizers=_string_list(metadata.get("finalizers")),
        cattle_conditions=_namespace_cattle_conditions(metadata),
        link_keys=sorted(_mapping_value(payload, "links") or {}),
        payload=dict(payload),
    )


async def rancher_namespace_get(
    namespace: str,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: SteveDiscoveryClient | None = None,
) -> RancherNamespaceDetail:
    """Fetch one downstream namespace by name."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_namespace_get(instance_name, cluster_id, namespace, client)
    async with RancherSteveClient(
        instance_name,
        instance_config,
        cluster_id=cluster_id,
    ) as steve_client:
        return await _fetch_namespace_get(instance_name, cluster_id, namespace, steve_client)


def register_project_namespace_tools(mcp: FastMCP) -> None:
    """Register curated project/namespace tools with the FastMCP server."""

    mcp.tool(name="rancher_projects_list")(rancher_projects_list_tool)
    mcp.tool(name="rancher_project_get")(rancher_project_get_tool)
    mcp.tool(name="rancher_namespaces_list")(rancher_namespaces_list_tool)
    mcp.tool(name="rancher_namespace_get")(rancher_namespace_get_tool)


async def rancher_projects_list_tool(
    cluster_id: str | None = None,
    state: str | None = None,
    limit: int | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherProjectList:
    """Public MCP wrapper for curated project list."""

    return await rancher_projects_list(
        cluster_id=cluster_id,
        state=state,
        limit=limit,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_project_get_tool(
    project_id: str,
    instance: str | None = None,
) -> RancherProjectDetail:
    """Public MCP wrapper for curated project detail."""

    return await rancher_project_get(
        project_id=project_id,
        instance=instance,
    )


async def rancher_namespaces_list_tool(
    cluster_id: str = "local",
    phase: str | None = None,
    project_id: str | None = None,
    limit: int | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    instance: str | None = None,
) -> RancherNamespaceList:
    """Public MCP wrapper for curated namespace list."""

    return await rancher_namespaces_list(
        cluster_id=cluster_id,
        phase=phase,
        project_id=project_id,
        limit=limit,
        label_selector=label_selector,
        field_selector=field_selector,
        instance=instance,
    )


async def rancher_namespace_get_tool(
    namespace: str,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherNamespaceDetail:
    """Public MCP wrapper for curated namespace detail."""

    return await rancher_namespace_get(
        namespace=namespace,
        cluster_id=cluster_id,
        instance=instance,
    )


def _build_project_query_params(
    *,
    cluster_id: str | None,
    state: str | None,
    limit: int | None,
    sort_by: str | None,
    reverse: bool | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher projects collection."""

    params: dict[str, str | int | bool] = {}
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if state is not None:
        params["state"] = state
    if limit is not None:
        params["limit"] = limit
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_namespace_query_params(
    *,
    project_id: str | None,
    limit: int | None,
    label_selector: str | None,
    field_selector: str | None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the downstream namespaces collection."""

    merged_label_selector = _merge_project_label_selector(label_selector, project_id)
    return build_steve_list_query_params(
        limit=limit,
        label_selector=merged_label_selector,
        field_selector=field_selector,
    )


def _project_summary_from_payload(payload: Mapping[str, object]) -> RancherProjectSummary:
    """Normalize one Rancher project payload."""

    labels = _mapping_value(payload, "labels") or {}
    return RancherProjectSummary(
        id=_string_value(payload, "id") or "<unknown-project>",
        name=_string_value(payload, "name") or "<unknown-project>",
        cluster_id=_string_value(payload, "clusterId"),
        state=_string_value(payload, "state"),
        description=_string_value(payload, "description"),
        monitoring_enabled=_bool_value(payload, "enableProjectMonitoring"),
        default_project=_label_true(labels, "authz.management.cattle.io/default-project"),
        system_project=_label_true(labels, "authz.management.cattle.io/system-project"),
        condition_types_true=_condition_types_true(payload),
    )


def _namespace_summary_from_payload(
    cluster_id: str,
    payload: Mapping[str, object],
) -> RancherNamespaceSummary:
    """Normalize one downstream namespace payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    annotations = _mapping_value(metadata, "annotations") or {}
    labels = _mapping_value(metadata, "labels") or {}
    state = _mapping_value(metadata, "state") or {}
    project_id_short = _string_value(labels, "field.cattle.io/projectId")
    return RancherNamespaceSummary(
        id=_string_value(payload, "id") or _string_value(metadata, "name") or "<unknown-namespace>",
        name=_string_value(metadata, "name") or "<unknown-namespace>",
        cluster_id=cluster_id,
        phase=_string_value(_mapping_value(payload, "status"), "phase"),
        state_name=_string_value(state, "name"),
        state_message=_string_value(state, "message"),
        state_error=_bool_value(state, "error"),
        project_id=_string_value(annotations, "field.cattle.io/projectId") or project_id_short,
        project_id_short=project_id_short,
        finalizer_count=len(_string_list(metadata.get("finalizers"))),
    )


def _conditions_from_payload(payload: Mapping[str, object]) -> list[RancherCondition]:
    """Normalize Rancher conditions from a payload."""

    raw_conditions = payload.get("conditions")
    if not isinstance(raw_conditions, list):
        return []
    conditions: list[RancherCondition] = []
    typed_conditions = cast(list[object], raw_conditions)
    for raw_condition in typed_conditions:
        if not isinstance(raw_condition, dict):
            continue
        condition = cast(dict[str, object], raw_condition)
        condition_type = _string_value(condition, "type")
        if condition_type is None:
            continue
        conditions.append(
            RancherCondition(
                type=condition_type,
                status=_string_value(condition, "status"),
                reason=_string_value(condition, "reason"),
                message=_string_value(condition, "message"),
            )
        )
    return conditions


def _namespace_cattle_conditions(metadata: Mapping[str, object]) -> list[RancherCondition]:
    """Parse Rancher namespace conditions from the embedded cattle status annotation."""

    annotations = _mapping_value(metadata, "annotations") or {}
    raw_status = _string_value(annotations, "cattle.io/status")
    if raw_status is None:
        return []
    try:
        decoded: object = json.loads(raw_status)
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, dict):
        return []
    typed_status = cast(dict[str, object], decoded)
    raw_conditions = typed_status.get("Conditions")
    if not isinstance(raw_conditions, list):
        return []
    conditions: list[RancherCondition] = []
    typed_conditions = cast(list[object], raw_conditions)
    for raw_condition in typed_conditions:
        if not isinstance(raw_condition, dict):
            continue
        condition = cast(dict[str, object], raw_condition)
        condition_type = _string_value(condition, "Type")
        if condition_type is None:
            continue
        conditions.append(
            RancherCondition(
                type=condition_type,
                status=_string_value(condition, "Status"),
                reason=_string_value(condition, "Reason"),
                message=_string_value(condition, "Message"),
            )
        )
    return conditions


def _condition_types_true(payload: Mapping[str, object]) -> list[str]:
    """Return sorted Rancher condition types whose status is true."""

    return sorted(
        condition.type
        for condition in _conditions_from_payload(payload)
        if _status_to_bool(condition.status) is True
    )


def _merge_project_label_selector(
    label_selector: str | None,
    project_id: str | None,
) -> str | None:
    """Merge a namespace project filter into any user-provided label selector."""

    project_selector = _project_label_selector(project_id)
    if project_selector is None:
        return label_selector
    if label_selector is None:
        return project_selector
    return f"{label_selector},{project_selector}"


def _project_label_selector(project_id: str | None) -> str | None:
    """Convert a Rancher project id into the namespace project label selector."""

    if project_id is None:
        return None
    if ":" in project_id:
        _, _, short_project_id = project_id.partition(":")
    else:
        short_project_id = project_id
    if not short_project_id:
        return None
    return f"field.cattle.io/projectId={short_project_id}"


def _label_true(labels: Mapping[str, object], key: str) -> bool | None:
    """Return one label value normalized as a boolean when possible."""

    return _status_to_bool(_string_value(labels, key))


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher list payload."""

    raw_items = payload.get("data")
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, object]] = []
    typed_items = cast(list[object], raw_items)
    for item in typed_items:
        if isinstance(item, dict):
            items.append(cast(dict[str, object], item))
    return items


def _mapping_value(
    payload: Mapping[str, object] | None,
    key: str,
) -> dict[str, object] | None:
    """Read one nested mapping value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    if not isinstance(raw_value, dict):
        return None
    return cast(dict[str, object], raw_value)


def _string_value(payload: Mapping[str, object] | None, key: str) -> str | None:
    """Read one string value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, str) else None


def _bool_value(payload: Mapping[str, object] | None, key: str) -> bool | None:
    """Read one boolean value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, bool) else None


def _string_dict(value: object) -> dict[str, str]:
    """Normalize an arbitrary value into a string-to-string mapping."""

    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, raw_value in cast(dict[object, object], value).items():
        if isinstance(key, str) and isinstance(raw_value, str):
            result[key] = raw_value
    return result


def _string_list(value: object) -> list[str]:
    """Normalize an arbitrary value into a list of strings."""

    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in cast(list[object], value):
        if isinstance(item, str):
            result.append(item)
    return result


def _status_to_bool(status: str | None) -> bool | None:
    """Normalize Rancher condition-style strings to booleans."""

    if status is None:
        return None
    lowered = status.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None
