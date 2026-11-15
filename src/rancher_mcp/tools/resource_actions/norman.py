"""Norman generic resource action and link tools."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import Context, Elicit, Resolve

from rancher_mcp.audit import audit_mutation
from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceActionResult, GenericResourceLinkResult
from rancher_mcp.rate_limit import rate_limit_writes
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resources import (
    build_resource_action_result,
    build_resource_item,
    build_resource_link_result,
    build_resource_path,
    parse_payload_object,
    resolve_resource_action_path,
    resolve_resource_link_path,
    schema_reference_from_payload,
)
from rancher_mcp.services.resources.paths import schema_path
from rancher_mcp.services.safety import ensure_instance_writable
from rancher_mcp.tools.support.approval_wording import action_question, generic_target
from rancher_mcp.tools.support.human_approval import (
    NOT_ASKED,
    Approval,
    HumanApproval,
    Unasked,
    ask_unless_pointless,
    settle,
)
from rancher_mcp.tools.support.json_args import OptionalJsonText


async def _fetch_norman_resource_action_invoke(
    instance_name: str,
    schema_id: str,
    resource_id: str,
    action_name: str,
    payload_json: str | None,
    client: ManagementDiscoveryClient,
) -> GenericResourceActionResult:
    """Invoke a Norman resource action."""

    schema_payload = await client.get_json(schema_path("/v3/schemas", schema_id))
    schema = schema_reference_from_payload(
        plane="norman",
        cluster_id=None,
        schema_id=schema_id,
        payload=schema_payload,
    )
    resource_path = build_resource_path(schema, resource_id=resource_id)
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
        schema_id=schema_id,
        resource_id=resource.id or resource_id,
        action_name=action_name,
        action_path=action_path,
        payload=response_payload,
    )


@audit_mutation(operation="action_invoke", plane="norman")
@rate_limit_writes
async def rancher_norman_resource_action_invoke(
    schema_id: str,
    resource_id: str,
    action_name: str,
    payload_json: OptionalJsonText = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> GenericResourceActionResult:
    """Invoke a Norman resource action by resource type and id. An action is a
    POST, so it is guarded like every other mutation — see ADR-0003."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    ensure_instance_writable(instance_name, instance_config)
    if client is not None:
        return await _fetch_norman_resource_action_invoke(
            instance_name, schema_id, resource_id, action_name, payload_json, client
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_norman_resource_action_invoke(
            instance_name, schema_id, resource_id, action_name, payload_json, managed_client
        )


async def _fetch_norman_resource_link_follow(
    instance_name: str,
    schema_id: str,
    resource_id: str,
    link_name: str,
    client: ManagementDiscoveryClient,
) -> GenericResourceLinkResult:
    """Follow a Norman resource link."""

    schema_payload = await client.get_json(schema_path("/v3/schemas", schema_id))
    schema = schema_reference_from_payload(
        plane="norman",
        cluster_id=None,
        schema_id=schema_id,
        payload=schema_payload,
    )
    resource_path = build_resource_path(schema, resource_id=resource_id)
    resource_payload = await client.get_json(resource_path)
    link_path = resolve_resource_link_path(
        link_name=link_name,
        payload=resource_payload,
    )
    response_payload = await client.get_json(link_path)
    resource = build_resource_item(
        plane="norman",
        cluster_id=None,
        payload=resource_payload,
    )
    return build_resource_link_result(
        instance=instance_name,
        plane="norman",
        schema_id=schema_id,
        resource_id=resource.id or resource_id,
        link_name=link_name,
        link_path=link_path,
        payload=response_payload,
    )


async def rancher_norman_resource_link_follow(
    schema_id: str,
    resource_id: str,
    link_name: str,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> GenericResourceLinkResult:
    """Follow a Norman resource link by resource type and id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_norman_resource_link_follow(
            instance_name,
            schema_id,
            resource_id,
            link_name,
            client,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_norman_resource_link_follow(
            instance_name,
            schema_id,
            resource_id,
            link_name,
            managed_client,
        )


async def _approve(
    ctx: Context[Any, Any],
    schema_id: str,
    resource_id: str,
    action_name: str,
    instance: str | None,
) -> Elicit[Approval] | Unasked:
    def question() -> str:
        instance_name, instance_config = resolve_instance(get_settings(), instance)
        ensure_instance_writable(instance_name, instance_config)
        target = generic_target(
            schema_id=schema_id, resource_id=resource_id, instance=instance_name
        )
        return action_question(action_name, target)

    return ask_unless_pointless(ctx, question)


async def rancher_norman_resource_action_invoke_tool(
    schema_id: str,
    resource_id: str,
    action_name: str,
    payload_json: OptionalJsonText = None,
    instance: str | None = None,
    approval: Annotated[HumanApproval, Resolve(_approve)] = NOT_ASKED,
) -> GenericResourceActionResult:
    """Invoke a named Norman resource action from that resource's own `actions`
    links, with an optional JSON body, and return its response — the escape
    hatch for lifecycle operations no curated tool wraps yet. Where the client
    can ask, a person is asked to approve it first (`APPROVAL_DENIED` if they
    refuse)."""

    settle(
        approval,
        tool_name="rancher_norman_resource_action_invoke",
        plane="norman",
        schema_id=schema_id,
        resource_id=resource_id,
        action_name=action_name,
        instance=instance,
    )
    return await rancher_norman_resource_action_invoke(
        schema_id=schema_id,
        resource_id=resource_id,
        action_name=action_name,
        payload_json=payload_json,
        instance=instance,
    )


async def rancher_norman_resource_link_follow_tool(
    schema_id: str,
    resource_id: str,
    link_name: str,
    instance: str | None = None,
) -> GenericResourceLinkResult:
    """Follow a named Norman resource link from that resource's own `links` map
    and return the linked payload — the escape hatch for related data no
    curated tool exposes yet."""

    return await rancher_norman_resource_link_follow(
        schema_id=schema_id,
        resource_id=resource_id,
        link_name=link_name,
        instance=instance,
    )
