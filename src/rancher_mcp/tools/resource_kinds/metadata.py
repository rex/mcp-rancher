"""Collapsed generic `set_labels` / `set_annotations` tools (F2 fix).

Replaces 42 + 42 per-resource-family generated tools
(`rancher_<kind>_set_labels` / `rancher_<kind>_set_annotations`, one pair
per resource family, each with its own arg name for "which object" —
`pod_name`, `volume_name`, `service_name`, ...) with two `resource_kind`-
dispatched tools sharing one uniform `name` argument.

Preserves, per call, everything the generated per-resource tools carried:
audit logging (`@audit_mutation`), write rate limiting
(`@rate_limit_writes`), the read-only-instance guard
(`ensure_instance_writable`), and the mutation-receipt response shape
(`RancherMutationReceipt`: a best-effort `before` snapshot of exactly the
changed metadata field, the applied `changed` subtree, and `duration_ms`)
— identical mechanics to the generated `_patch_<kind>_set_labels` /
`_patch_<kind>_set_annotations` functions this pack replaces (see
`rancher_mcp.tools.support.mutations.fetch_patch_before`).
"""

from __future__ import annotations

import time
from typing import Literal

from rancher_mcp.audit import audit_mutation
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.models.resources import RancherMutationReceipt
from rancher_mcp.rate_limit import rate_limit_writes
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.services.safety import ensure_instance_writable
from rancher_mcp.tools.resource_kinds._generated_kinds import (
    AnnotatableResourceKind,
    LabelableResourceKind,
)
from rancher_mcp.tools.resource_kinds.shared import (
    GenericMutationClient,
    open_mutation_client,
    resolve_kind,
    resolve_namespace,
)
from rancher_mcp.tools.support.mutations import fetch_patch_before

_MetadataField = Literal["labels", "annotations"]


async def _set_metadata_field(
    field: _MetadataField,
    instance_name: str,
    resource_kind: str,
    name: str,
    cluster_id: str,
    namespace: str | None,
    values: dict[str, str],
    client: GenericMutationClient,
) -> RancherMutationReceipt:
    """Shared merge-patch mechanics for `set_labels` / `set_annotations` —
    both target `metadata.<field>` with full-map-replacement semantics."""

    spec = resolve_kind(resource_kind)
    resolved_namespace = resolve_namespace(spec, namespace)
    path = spec.detail_path(cluster_id, resolved_namespace, name)
    patch_subtree: dict[str, object] = {field: values}
    request_payload: dict[str, object] = {"metadata": patch_subtree}

    before = await fetch_patch_before(
        lambda: client.get_json(path),
        target_path="metadata",
        patch_subtree=patch_subtree,
        kind=spec.kind,
        action=f"set_{field}",
        name=name,
    )
    started_at = time.monotonic()
    await client.patch_json(path, payload=request_payload)
    duration_ms = int((time.monotonic() - started_at) * 1000)
    return RancherMutationReceipt(
        instance=instance_name,
        plane=spec.plane,
        action=f"set_{field}",
        kind=spec.kind,
        name=name,
        cluster_id=cluster_id,
        namespace=resolved_namespace,
        changed=dict(patch_subtree),
        before=before,
        duration_ms=duration_ms,
        suggested_next_steps=[spec.get_tool, spec.list_tool],
    )


@audit_mutation(operation="resource_set_labels", plane="steve")
@rate_limit_writes
async def rancher_resource_set_labels(
    resource_kind: LabelableResourceKind,
    name: str,
    labels: dict[str, str],
    cluster_id: str = "local",
    namespace: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: GenericMutationClient | None = None,
) -> RancherMutationReceipt:
    """Replace metadata.labels on one resource via JSON merge-patch."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    ensure_instance_writable(instance_name, instance_config)
    if client is not None:
        return await _set_metadata_field(
            "labels", instance_name, resource_kind, name, cluster_id, namespace, labels, client
        )
    spec = resolve_kind(resource_kind)
    async with open_mutation_client(
        instance_name, instance_config, cluster_id, spec.transport
    ) as opened_client:
        return await _set_metadata_field(
            "labels",
            instance_name,
            resource_kind,
            name,
            cluster_id,
            namespace,
            labels,
            opened_client,
        )


async def rancher_resource_set_labels_tool(
    resource_kind: LabelableResourceKind,
    name: str,
    labels: dict[str, str],
    cluster_id: str = "local",
    namespace: str | None = None,
    instance: str | None = None,
) -> RancherMutationReceipt:
    """Replace metadata.labels on one resource of any labelable kind via JSON
    merge-patch. The `labels` arg is a complete replacement map — pass {} to
    remove all labels. `resource_kind` selects the resource family (pod,
    deployment, config_map, secret, ...); `name` is that resource's own
    name (uniform across every kind — no more per-family `pod_name` /
    `service_name` / `volume_name`). `namespace` is required for namespaced
    kinds and ignored for cluster-scoped ones (e.g. storage_class,
    priority_class). Returns a compact mutation receipt — the before/after
    of just the labels field plus timing, not the full resource. Subject to
    write rate limiting and audit logging."""

    return await rancher_resource_set_labels(
        resource_kind=resource_kind,
        name=name,
        labels=labels,
        cluster_id=cluster_id,
        namespace=namespace,
        instance=instance,
    )


@audit_mutation(operation="resource_set_annotations", plane="steve")
@rate_limit_writes
async def rancher_resource_set_annotations(
    resource_kind: AnnotatableResourceKind,
    name: str,
    annotations: dict[str, str],
    cluster_id: str = "local",
    namespace: str | None = None,
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: GenericMutationClient | None = None,
) -> RancherMutationReceipt:
    """Replace metadata.annotations on one resource via JSON merge-patch."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    ensure_instance_writable(instance_name, instance_config)
    if client is not None:
        return await _set_metadata_field(
            "annotations",
            instance_name,
            resource_kind,
            name,
            cluster_id,
            namespace,
            annotations,
            client,
        )
    spec = resolve_kind(resource_kind)
    async with open_mutation_client(
        instance_name, instance_config, cluster_id, spec.transport
    ) as opened_client:
        return await _set_metadata_field(
            "annotations",
            instance_name,
            resource_kind,
            name,
            cluster_id,
            namespace,
            annotations,
            opened_client,
        )


async def rancher_resource_set_annotations_tool(
    resource_kind: AnnotatableResourceKind,
    name: str,
    annotations: dict[str, str],
    cluster_id: str = "local",
    namespace: str | None = None,
    instance: str | None = None,
) -> RancherMutationReceipt:
    """Replace metadata.annotations on one resource of any annotatable kind
    via JSON merge-patch. The `annotations` arg is a complete replacement
    map — pass {} to remove all annotations. `resource_kind` selects the
    resource family; `name` is that resource's own name (uniform across
    every kind). `namespace` is required for namespaced kinds and ignored
    for cluster-scoped ones. Returns a compact mutation receipt. Subject to
    write rate limiting and audit logging."""

    return await rancher_resource_set_annotations(
        resource_kind=resource_kind,
        name=name,
        annotations=annotations,
        cluster_id=cluster_id,
        namespace=namespace,
        instance=instance,
    )
