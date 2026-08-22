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

from rancher_mcp.audit import audit_mutation
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.models.resources import RancherCuratedDeleteResult
from rancher_mcp.rate_limit import rate_limit_writes
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.safety import ensure_instance_writable
from rancher_mcp.tools.resource_kinds._generated_kinds import DeletableResourceKind
from rancher_mcp.tools.resource_kinds.shared import (
    GenericMutationClient,
    delete_confirmation_phrase,
    open_mutation_client,
    resolve_kind,
    resolve_namespace,
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
    actually needs."""

    spec = resolve_kind(resource_kind)
    resolved_namespace = resolve_namespace(spec, namespace)
    expected_phrase = delete_confirmation_phrase(spec, name, resolved_namespace)
    if confirmation != expected_phrase:
        raise RancherCapabilityError(
            f"Delete confirmation did not match the required phrase: {expected_phrase!r}"
        )
    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    ensure_instance_writable(instance_name, instance_config)
    if client is not None:
        return await _delete_resource(
            instance_name,
            resource_kind,
            name,
            cluster_id,
            resolved_namespace,
            expected_phrase,
            client,
        )
    async with open_mutation_client(
        instance_name, instance_config, cluster_id, spec.transport
    ) as opened_client:
        return await _delete_resource(
            instance_name,
            resource_kind,
            name,
            cluster_id,
            resolved_namespace,
            expected_phrase,
            opened_client,
        )


async def rancher_resource_delete_tool(
    resource_kind: DeletableResourceKind,
    name: str,
    confirmation: str,
    cluster_id: str = "local",
    namespace: str | None = None,
    instance: str | None = None,
) -> RancherCuratedDeleteResult:
    """Delete one resource of any deletable kind and return a typed receipt
    of what was removed. Destructive and irreversible. `resource_kind`
    selects the resource family (pod, deployment, config_map, secret, ...);
    `name` is that resource's own name (uniform across every kind).
    `namespace` is required for namespaced kinds, ignored for cluster-scoped
    ones. The caller MUST first echo the exact confirmation phrase this
    kind requires: `"delete <kind> <name>"`, plus `" in namespace
    <namespace>"` for namespaced kinds — call this tool without a matching
    `confirmation` first to see the required phrase in the error. Subject
    to write rate limiting and audit logging."""

    return await rancher_resource_delete(
        resource_kind=resource_kind,
        name=name,
        confirmation=confirmation,
        cluster_id=cluster_id,
        namespace=namespace,
        instance=instance,
    )
