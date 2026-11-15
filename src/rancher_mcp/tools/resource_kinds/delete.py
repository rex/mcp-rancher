"""Collapsed generic `delete` tool (F2 fix).

Replaces 34 per-resource-family generated `rancher_<kind>_delete` tools with
one `resource_kind`-dispatched tool sharing a uniform `name` argument.
Destructive — preserves the exact confirmation-phrase guard the generated
per-resource delete tools used (``delete <kind> <name>`` [``in namespace
<namespace>``]): the phrase must be echoed back verbatim, checked BEFORE any
HTTP call is made, plus audit logging (`@audit_mutation`), write rate
limiting (`@rate_limit_writes`), and the read-only-instance guard
(`ensure_instance_writable`) — identical mechanics to the generated
`_delete_<kind>` functions this pack replaces.
"""

from __future__ import annotations

from typing import Annotated, Any, NamedTuple

from mcp.server.mcpserver import Context, Elicit, Resolve

from rancher_mcp.audit import audit_mutation
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.identifiers import require_safe_identifier
from rancher_mcp.models.discovery import RancherInstanceConfig
from rancher_mcp.models.resources import RancherCuratedDeleteResult
from rancher_mcp.rate_limit import rate_limit_writes
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.safety import ensure_instance_writable
from rancher_mcp.tools.resource_kinds._generated_kinds import (
    DeletableResourceKind,
    ResourceKindSpec,
)
from rancher_mcp.tools.resource_kinds.shared import (
    GenericMutationClient,
    delete_confirmation_phrase,
    open_mutation_client,
    resolve_kind,
    resolve_namespace,
)
from rancher_mcp.tools.support.approval_wording import delete_question, describe_target
from rancher_mcp.tools.support.human_approval import (
    NOT_ASKED,
    Approval,
    HumanApproval,
    Unasked,
    ask_unless_pointless,
    settle,
)


async def _delete_resource(
    instance_name: str,
    resource_kind: str,
    name: str,
    cluster_id: str,
    resolved_namespace: str | None,
    confirmation_phrase_used: str,
    client: GenericMutationClient,
) -> RancherCuratedDeleteResult:
    """Delete one resource of *resource_kind*; returns a typed delete result.

    ``resolved_namespace`` is ALREADY validated (`resolve_namespace` — the
    caller must have resolved it once to compute ``confirmation_phrase_used``
    in the first place) rather than re-derived here, so there is exactly one
    place a namespaced-kind-missing-namespace refusal can happen.
    """

    spec = resolve_kind(resource_kind)
    path = spec.detail_path(cluster_id, resolved_namespace, name)
    response_payload = await client.delete_json(path)
    return RancherCuratedDeleteResult(
        instance=instance_name,
        plane=spec.plane,
        resource_kind=spec.kind,
        resource_name=name,
        namespace=resolved_namespace,
        cluster_id=cluster_id,
        deleted=True,
        confirmation_phrase_used=confirmation_phrase_used,
        response_payload=dict(response_payload),
        suggested_next_steps=[spec.list_tool],
    )


@audit_mutation(operation="resource_delete", plane="steve")
@rate_limit_writes
async def rancher_resource_delete(
    resource_kind: DeletableResourceKind,
    name: str,
    confirmation: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: GenericMutationClient | None = None,
) -> RancherCuratedDeleteResult:
    """Delete one resource after the agent echoes the required confirmation
    phrase. Namespace requiredness is resolved (and the confirmation
    phrase's shape decided) from `resource_kind`'s spec BEFORE the phrase
    is checked, so the expected phrase always matches what the kind
    actually needs.

    The read-only check comes first of all. A caller who is told the phrase
    was wrong will go and work out the right one, only to be refused again on
    the next call for a reason no phrase can fix."""

    target = _preflight(resource_kind, name, confirmation, namespace, instance, settings)
    require_safe_identifier("cluster_id", cluster_id, single_segment=True)
    if client is not None:
        return await _delete_resource(
            target.instance_name,
            resource_kind,
            name,
            cluster_id,
            target.namespace,
            target.phrase,
            client,
        )
    async with open_mutation_client(
        target.instance_name, target.instance_config, cluster_id, target.spec.transport
    ) as opened_client:
        return await _delete_resource(
            target.instance_name,
            resource_kind,
            name,
            cluster_id,
            target.namespace,
            target.phrase,
            opened_client,
        )


class _DeleteTarget(NamedTuple):
    """What a delete resolved to once every local check has passed."""

    instance_name: str
    instance_config: RancherInstanceConfig
    spec: ResourceKindSpec
    namespace: str | None
    phrase: str


def _preflight(
    resource_kind: str,
    name: str,
    confirmation: str,
    namespace: str | None,
    instance: str | None,
    settings: AppSettings | None,
) -> _DeleteTarget:
    """Every check that needs no network, in the order a caller should hear of
    them. Shared by the delete itself and by the question put to a person, so
    nobody is asked to approve a call these would refuse."""

    instance_name, instance_config = resolve_instance(settings or get_settings(), instance)
    ensure_instance_writable(instance_name, instance_config)
    spec = resolve_kind(resource_kind)
    # One plain name each. A `..` here used to be sent as it stood, and the
    # HTTP library resolved it: deleting a "pod" named `..` deleted its
    # namespace, under a phrase, a prompt and an audit record that said "pod".
    require_safe_identifier("name", name, single_segment=True)
    resolved_namespace = resolve_namespace(spec, namespace)
    if resolved_namespace is not None:
        require_safe_identifier("namespace", resolved_namespace, single_segment=True)
    expected_phrase = delete_confirmation_phrase(spec, name, resolved_namespace)
    if confirmation != expected_phrase:
        raise RancherCapabilityError(
            f"Delete confirmation did not match the required phrase: {expected_phrase!r}"
        )
    return _DeleteTarget(instance_name, instance_config, spec, resolved_namespace, expected_phrase)


async def _approve(
    ctx: Context[Any, Any],
    resource_kind: str,
    name: str,
    confirmation: str,
    cluster_id: str,
    namespace: str | None,
    instance: str | None,
) -> Elicit[Approval] | Unasked:
    def question() -> str:
        target = _preflight(resource_kind, name, confirmation, namespace, instance, None)
        return delete_question(
            describe_target(
                what=target.spec.kind.replace("_", " "),
                name=name,
                instance=target.instance_name,
                cluster_id=cluster_id,
                namespace=target.namespace,
            )
        )

    return ask_unless_pointless(ctx, question)


async def rancher_resource_delete_tool(
    resource_kind: DeletableResourceKind,
    name: str,
    confirmation: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    instance: str | None = None,
    approval: Annotated[HumanApproval, Resolve(_approve)] = NOT_ASKED,
) -> RancherCuratedDeleteResult:
    """Delete one resource of any deletable kind and return a typed receipt
    of what was removed. Destructive and irreversible. `resource_kind`
    selects the resource family (pod, deployment, config_map, secret, ...);
    `name` is that resource's own name (uniform across every kind).
    `namespace` is required for namespaced kinds, ignored for cluster-scoped
    ones. The caller MUST first echo the exact confirmation phrase this
    kind requires: `"delete <kind> <name>"`, plus `" in namespace
    <namespace>"` for namespaced kinds — call this tool without a matching
    `confirmation` first to see the required phrase in the error. Where the
    client can ask, a person is asked to approve it too; their refusal comes
    back as `APPROVAL_DENIED`. Subject to write rate limiting and audit
    logging."""

    settle(
        approval,
        tool_name="rancher_resource_delete",
        plane="steve",
        resource_kind=resource_kind,
        resource_id=name,
        cluster_id=cluster_id,
        namespace=namespace,
        instance=instance,
    )
    return await rancher_resource_delete(
        resource_kind=resource_kind,
        name=name,
        confirmation=confirmation,
        cluster_id=cluster_id,
        namespace=namespace,
        instance=instance,
    )
