"""Steve generic resource apply implementation."""

from __future__ import annotations

import json
from typing import Annotated, Any

from mcp.server.mcpserver import Context, Elicit, Resolve

from rancher_mcp.audit import audit_mutation
from rancher_mcp.clients.management import ManagementMutationClient, RancherManagementClient
from rancher_mcp.clients.steve import RancherSteveClient, SteveDiscoveryClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import GenericResourceMutationResult
from rancher_mcp.rate_limit import rate_limit_writes
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.resource_queries import build_steve_apply_query_params
from rancher_mcp.services.resources import (
    build_k8s_proxy_resource_path,
    build_resource_mutation_result,
)
from rancher_mcp.services.resources.capabilities import (
    ensure_apply_supported,
    restrict_payload_fields,
)
from rancher_mcp.services.resources.contexts import load_steve_resource_context
from rancher_mcp.services.resources.schema import parse_required_payload_object
from rancher_mcp.services.safety import ensure_instance_writable
from rancher_mcp.tools.support.approval_wording import change_question, generic_target
from rancher_mcp.tools.support.human_approval import (
    NOT_ASKED,
    Approval,
    HumanApproval,
    KeepGoing,
    Unasked,
    ask_unless_pointless,
    settle,
)
from rancher_mcp.tools.support.json_args import OptionalJsonText


async def _apply_steve_resource(
    instance_name: str,
    cluster_id: str,
    namespace: str | None,
    schema_id: str,
    resource_id: str,
    payload_json: str,
    field_manager: str,
    force: bool | None,
    params_json: str | None,
    steve_client: SteveDiscoveryClient,
    management_client: ManagementMutationClient,
) -> GenericResourceMutationResult:
    """Apply one Steve resource via Kubernetes server-side apply."""

    context = await load_steve_resource_context(
        cluster_id=cluster_id,
        namespace=namespace,
        schema_id=schema_id,
        resource_id=resource_id,
        steve_client=steve_client,
    )
    ensure_apply_supported(context.schema)
    request_payload = restrict_payload_fields(
        parse_required_payload_object(payload_json),
        context.schema.updatable_fields,
    )
    request_path = build_k8s_proxy_resource_path(
        context.schema,
        cluster_id=cluster_id,
        resource_id=context.resource.name or resource_id,
        namespace=context.resource.namespace or namespace,
    )
    response_payload = await management_client.patch_content_json(
        request_path,
        content=json.dumps(request_payload),
        content_type="application/apply-patch+yaml",
        params=build_steve_apply_query_params(
            field_manager=field_manager,
            force=force,
            params_json=params_json,
        ),
    )
    return build_resource_mutation_result(
        instance=instance_name,
        plane="steve",
        schema_id=schema_id,
        operation="apply",
        request_method="PATCH",
        request_path=request_path,
        payload=response_payload,
        cluster_id=cluster_id,
        namespace=context.resource.namespace or namespace,
        resource_id_hint=context.resource.id or resource_id,
        resource_path_hint=request_path,
    )


@audit_mutation(operation="apply", plane="steve")
@rate_limit_writes
async def rancher_steve_resource_apply(
    schema_id: str,
    resource_id: str,
    payload_json: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    field_manager: str = "rancher-mcp",
    force: bool | None = None,
    params_json: OptionalJsonText = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    steve_client: SteveDiscoveryClient | None = None,
    management_client: ManagementMutationClient | None = None,
) -> GenericResourceMutationResult:
    """Apply one Steve resource by schema type and id."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    ensure_instance_writable(instance_name, instance_config)
    if steve_client is not None and management_client is not None:
        return await _apply_steve_resource(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            resource_id,
            payload_json,
            field_manager,
            force,
            params_json,
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
        return await _apply_steve_resource(
            instance_name,
            cluster_id,
            namespace,
            schema_id,
            resource_id,
            payload_json,
            field_manager,
            force,
            params_json,
            proxy_client,
            managed_client,
        )


_TOOL = "rancher_steve_resource_apply"


async def _approve(
    ctx: Context[Any, Any],
    schema_id: str,
    resource_id: str,
    payload_json: str,
    cluster_id: str,
    namespace: str | None,
    field_manager: str,
    force: bool | None,
    params_json: str | None,
    instance: str | None,
) -> Elicit[Approval] | Unasked:
    def question() -> str:
        instance_name, instance_config = resolve_instance(get_settings(), instance)
        ensure_instance_writable(instance_name, instance_config)
        target = generic_target(
            schema_id=schema_id,
            resource_id=resource_id,
            instance=instance_name,
            cluster_id=cluster_id,
            namespace=namespace,
        )
        # The same query the request will carry, so `force` — which takes
        # fields away from whoever owns them — is on the page.
        build_steve_apply_query_params(
            field_manager=field_manager, force=force, params_json=params_json
        )
        return change_question(
            "Apply to",
            target,
            payload_json=payload_json,
            params_json=params_json,
            options={"force": force} if force is not None else None,
        )

    return ask_unless_pointless(ctx, question, KeepGoing(_TOOL, instance, cluster_id))


async def rancher_steve_resource_apply_tool(
    schema_id: str,
    resource_id: str,
    payload_json: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    field_manager: str = "rancher-mcp",
    force: bool | None = None,
    params_json: OptionalJsonText = None,
    instance: str | None = None,
    approval: Annotated[HumanApproval, Resolve(_approve)] = NOT_ASKED,
) -> GenericResourceMutationResult:
    """Apply one Steve Kubernetes-proxy resource via Kubernetes server-side apply
    under any schema id and return the updated object — the untyped escape hatch
    for updates with no curated apply tool yet. Where the client can ask, a
    person is asked to approve it first, and may let further applies on that
    cluster through unasked for a while (`APPROVAL_DENIED` if they refuse)."""

    settle(
        approval,
        tool_name=_TOOL,
        plane="steve",
        schema_id=schema_id,
        resource_id=resource_id,
        cluster_id=cluster_id,
        namespace=namespace,
        instance=instance,
    )
    return await rancher_steve_resource_apply(
        schema_id=schema_id,
        resource_id=resource_id,
        payload_json=payload_json,
        cluster_id=cluster_id,
        namespace=namespace,
        field_manager=field_manager,
        force=force,
        params_json=params_json,
        instance=instance,
    )
