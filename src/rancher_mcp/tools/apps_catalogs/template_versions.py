"""Curated Rancher template-version tools."""

from __future__ import annotations

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.apps_catalogs import (
    RancherTemplateVersionDetail,
    RancherTemplateVersionList,
)
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.apps_catalogs.shared import (
    build_template_version_query_params,
    data_items,
    file_names_from_value,
    template_version_summary_from_payload,
)
from rancher_mcp.tools.support.values import mapping_value


async def _fetch_template_versions_list(
    instance_name: str,
    limit: int | None,
    external_id: str | None,
    version: str | None,
    version_name: str | None,
    state: str | None,
    sort_by: str | None,
    reverse: bool | None,
    client: ManagementDiscoveryClient,
) -> RancherTemplateVersionList:
    """Fetch and normalize the Rancher template-versions collection."""

    query_params = build_template_version_query_params(
        limit=limit,
        external_id=external_id,
        version=version,
        version_name=version_name,
        state=state,
        sort_by=sort_by,
        reverse=reverse,
    )
    payload = await client.get_json("/v3/templateversions", params=query_params or None)
    template_versions = [
        template_version_summary_from_payload(item) for item in data_items(payload)
    ]
    return RancherTemplateVersionList(
        instance=instance_name,
        template_version_count=len(template_versions),
        applied_query_params=query_params,
        template_versions=template_versions,
    )


async def rancher_template_versions_list(
    limit: int | None = None,
    external_id: str | None = None,
    version: str | None = None,
    version_name: str | None = None,
    state: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherTemplateVersionList:
    """List Rancher template versions with typed summaries."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_template_versions_list(
            instance_name,
            limit,
            external_id,
            version,
            version_name,
            state,
            sort_by,
            reverse,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_template_versions_list(
            instance_name,
            limit,
            external_id,
            version,
            version_name,
            state,
            sort_by,
            reverse,
            managed_client,
        )


async def _fetch_template_version_get(
    template_version_id: str,
    client: ManagementDiscoveryClient,
) -> RancherTemplateVersionDetail:
    """Fetch and normalize one Rancher template version."""

    payload = await client.get_json(f"/v3/templateversions/{template_version_id}")
    detail = RancherTemplateVersionDetail.model_validate(payload)
    file_names = file_names_from_value(payload.get("files"))
    return detail.model_copy(
        update={
            "file_names": file_names,
            "file_count": len(file_names),
            "question_count": len(detail.questions),
            "link_keys": sorted(mapping_value(payload, "links") or {}),
            "payload": dict(payload),
        }
    )


async def rancher_template_version_get(
    template_version_id: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherTemplateVersionDetail:
    """Fetch one Rancher template version by id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_template_version_get(template_version_id, client)
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_template_version_get(template_version_id, managed_client)


async def rancher_template_versions_list_tool(
    limit: int | None = None,
    external_id: str | None = None,
    version: str | None = None,
    version_name: str | None = None,
    state: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    instance: str | None = None,
) -> RancherTemplateVersionList:
    """Public MCP wrapper for curated template-version list."""

    return await rancher_template_versions_list(
        limit=limit,
        external_id=external_id,
        version=version,
        version_name=version_name,
        state=state,
        sort_by=sort_by,
        reverse=reverse,
        instance=instance,
    )


async def rancher_template_version_get_tool(
    template_version_id: str,
    instance: str | None = None,
) -> RancherTemplateVersionDetail:
    """Public MCP wrapper for curated template-version detail."""

    return await rancher_template_version_get(
        template_version_id=template_version_id,
        instance=instance,
    )
