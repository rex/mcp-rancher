"""Steve generic resource action implementation."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import Context, Elicit, Resolve

from rancher_mcp.audit import audit_mutation
from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceActionResult
from rancher_mcp.rate_limit import rate_limit_writes
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resources import (
    build_resource_action_result,
    parse_payload_object,
    resolve_resource_action_path,
)
from rancher_mcp.services.safety import ensure_instance_writable
from rancher_mcp.tools.resource_actions.steve_common import load_steve_resource_context
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


async def _fetch_steve_resource_action_invoke(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    schema_id: str,
    resource_id: str,
    action_name: str,
    payload_json: str | None,
    steve_client: SteveDiscoveryClient,
    management_client: ManagementDiscoveryClient,
) -> GenericResourceActionResult:
    """Invoke a Steve resource action."""

    context = await load_steve_resource_context(
        cluster_id=cluster_id,
        namespace=namespace,
        schema_id=schema_id,
        resource_id=resource_id,
        steve_client=steve_client,
    )
    action_path = resolve_resource_action_path(
        action_name=action_name,
        payload=context.resource_payload,
    )
    response_payload = await management_client.post_json(
        action_path,
        payload=parse_payload_object(payload_json),
    )
    return build_resource_action_result(
        instance=instance_name,
        plane="steve",
        schema_id=schema_id,
        resource_id=context.resource.id or resource_id,
        action_name=action_name,
        cluster_id=cluster_id,
        namespace=context.resource.namespace or namespace,
        action_path=action_path,
        payload=response_payload,
    )


@audit_mutation(operation="action_invoke", plane="steve")
@rate_limit_writes
async def rancher_steve_resource_action_invoke(
    schema_id: str,
    resource_id: str,
    action_name: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    payload_json: OptionalJsonText = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    steve_client: SteveDiscoveryClient | None = None,
    management_client: ManagementDiscoveryClient | None = None,
) -> GenericResourceActionResult:
    """Invoke a Steve resource action by resource type and id.

    An action is a POST: whatever it is called, it can change the resource.
    So this carries the same three guards as every other mutation — audited,
    rate limited, and refused on a read-only instance before anything is sent.
    """

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    ensure_instance_writable(instance_name, instance_config)
    if steve_client is not None and management_client is not None:
        return await _fetch_steve_resource_action_invoke(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            resource_id,
            action_name,
            payload_json,
            steve_client,
            management_client,
        )
    async with (
        RancherManagementClient(instance_name, instance_config) as managed_client,
        RancherSteveClient(
            instance_name,
            instance_config,
            cluster_id=cluster_id,
        ) as proxy_client,
    ):
        return await _fetch_steve_resource_action_invoke(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            resource_id,
            action_name,
            payload_json,
            proxy_client,
            managed_client,
        )


async def _approve(
    ctx: Context[Any, Any],
    schema_id: str,
    resource_id: str,
    action_name: str,
    cluster_id: str,
    namespace: str | None,
    instance: str | None,
) -> Elicit[Approval] | Unasked:
    def question() -> str:
        instance_name, instance_config = resolve_instance(get_settings(), instance)
        ensure_instance_writable(instance_name, instance_config)
        return action_question(
            action_name,
            generic_target(
                schema_id=schema_id,
                resource_id=resource_id,
                instance=instance_name,
                cluster_id=cluster_id,
                namespace=namespace,
            ),
        )

    return ask_unless_pointless(ctx, question)


async def rancher_steve_resource_action_invoke_tool(
    schema_id: str,
    resource_id: str,
    action_name: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    payload_json: OptionalJsonText = None,
    instance: str | None = None,
    approval: Annotated[HumanApproval, Resolve(_approve)] = NOT_ASKED,
) -> GenericResourceActionResult:
    """Invoke a named Steve Kubernetes-proxy resource action with an optional JSON
    body and return its response — the escape hatch for lifecycle operations no
    curated tool wraps yet. Where the client can ask, a person is asked to
    approve it first (`APPROVAL_DENIED` if they refuse)."""

    settle(
        approval,
        tool_name="rancher_steve_resource_action_invoke",
        plane="steve",
        schema_id=schema_id,
        resource_id=resource_id,
        action_name=action_name,
        cluster_id=cluster_id,
        namespace=namespace,
        instance=instance,
    )
    return await rancher_steve_resource_action_invoke(
        schema_id=schema_id,
        resource_id=resource_id,
        action_name=action_name,
        cluster_id=cluster_id,
        namespace=namespace,
        payload_json=payload_json,
        instance=instance,
    )
