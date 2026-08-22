"""Shared routing/safety helpers for the collapsed generic resource-kind
mutation tools (`rancher_resource_set_labels` / `_set_annotations` /
`_delete` — see `mutations.py` / `delete.py`).

F2 fix: a field operator reported four different "which object" argument
conventions (`name`, `service_name`, `volume_name`, `resource_id`) across
the per-resource generated tools this pack replaces. Every tool here uses
one uniform `name` argument and a closed `resource_kind` enum
(`_generated_kinds.LabelableResourceKind` / `DeletableResourceKind`) instead
of a bespoke tool per resource family.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from rancher_mcp.clients.management import RancherManagementClient
from rancher_mcp.clients.steve import RancherSteveClient
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.models.discovery import RancherInstanceConfig
from rancher_mcp.tools.resource_kinds._generated_kinds import (
    RESOURCE_KIND_REGISTRY,
    ResourceKindSpec,
)


class GenericMutationClient(Protocol):
    """The subset of client behavior these tools need.

    Both `RancherSteveClient` (`transport: steve` kinds — pods, services,
    namespaces) and `RancherManagementClient` (`transport: k8s-proxy` — every
    other kind) satisfy this structurally: their `get_json`/`patch_json`/
    `delete_json` signatures are already identical (see
    `clients/steve.py::SteveMutationClient` and
    `clients/management.py::ManagementMutationClient`), so one dispatch path
    can open whichever client a kind's `transport` calls for."""

    async def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]: ...

    async def patch_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]: ...

    async def delete_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]: ...


def resolve_kind(resource_kind: str) -> ResourceKindSpec:
    """Look up one resource kind's routing spec.

    `resource_kind` is typed `LabelableResourceKind` / `AnnotatableResourceKind`
    / `DeletableResourceKind` (closed `Literal`s) on every public tool
    signature, so FastMCP's own JSON-schema `enum` validation rejects an
    unknown kind before this ever runs in normal MCP use. This guard exists
    for direct Python callers (tests, the `client=` bypass path) and keeps
    the error message actionable rather than a raw `KeyError`.
    """

    spec = RESOURCE_KIND_REGISTRY.get(resource_kind)
    if spec is None:
        raise RancherCapabilityError(
            f"Unknown resource_kind {resource_kind!r}. "
            f"Valid kinds: {sorted(RESOURCE_KIND_REGISTRY)}"
        )
    return spec


def resolve_namespace(spec: ResourceKindSpec, namespace: str | None) -> str | None:
    """Enforce namespace requiredness for one kind; return the value to use.

    `namespace` is optional in every collapsed tool's Python/JSON-schema
    signature (one signature spans both namespaced and cluster-scoped
    kinds — a static "required" can't depend on the VALUE of another
    parameter). This is the runtime half of that contract: a namespaced
    kind called with no namespace is a clear, actionable refusal instead of
    a confusing downstream 404; a cluster-scoped kind's namespace (if one
    was passed anyway) is deliberately ignored rather than rejected — the
    old per-resource tools for those kinds never had a `namespace`
    parameter at all, so there was never a way to "wrongly" supply one.
    """

    if not spec.namespaced:
        return None
    if namespace is None:
        raise RancherCapabilityError(
            f"resource_kind={spec.kind!r} is namespaced; `namespace` is required "
            f"(pass the namespace the {spec.kind.replace('_', ' ')} lives in)"
        )
    return namespace


def delete_confirmation_phrase(spec: ResourceKindSpec, name: str, namespace: str | None) -> str:
    """The exact phrase a delete caller must echo back (same convention the
    pre-collapse per-resource delete tools used: ``delete <kind> <name>``,
    plus ``in namespace <namespace>`` for namespaced kinds)."""

    phrase = f"delete {spec.kind} {name}"
    if spec.namespaced:
        phrase += f" in namespace {namespace}"
    return phrase


def open_mutation_client(
    instance_name: str,
    instance_config: RancherInstanceConfig,
    cluster_id: str,
    transport: str,
) -> RancherSteveClient | RancherManagementClient:
    """Construct (but do not enter) the right client type for *transport*."""

    if transport == "steve":
        return RancherSteveClient(instance_name, instance_config, cluster_id=cluster_id)
    return RancherManagementClient(instance_name, instance_config)
