"""Build emission plans from descriptors.

A plan is a per-pack data structure ready for Jinja rendering. It holds:

- the resolved descriptor list for that pack
- per-descriptor template context (paths, model class names, helper
  functions injected as Jinja globals like `qp_type`)
- pack-level register block (sorted import groups, register entries,
  the union of annotation imports needed)

Keeping this between descriptor.py and emitter.py prevents the templates
from doing complex computation in Jinja and prevents the descriptor
schema from carrying derived fields.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field

from scripts.codegen.descriptor import Descriptor, PackDescriptor, ToolMeta

QP_TYPES: Mapping[str, str] = {
    # Steve / k8s-proxy
    "limit": "int",
    "label_selector": "str",
    "field_selector": "str",
    "continue_token": "str",
    # Norman
    "state": "str",
    "source": "str",
    "customized": "bool",
    "enabled": "bool",
    "sort_by": "str",
    "reverse": "bool",
    "marker": "str",
    "cluster_id": "str",
    "me": "bool",
    "severity": "str",
    "name": "str",
    "provider_type": "str",
    "access_mode": "str",
    # apps_catalogs
    "kind": "str",
    "helm_version": "str",
    "catalog_id": "str",
    "category": "str",
    "project_id": "str",
    "external_id": "str",
    "version": "str",
    "version_name": "str",
    # rbac
    "builtin": "bool",
    "new_user_default": "bool",
    "context": "str",
    "administrative": "bool",
    "cluster_creator_default": "bool",
    "project_creator_default": "bool",
    "external": "bool",
    "hidden": "bool",
    "locked": "bool",
    "global_role_id": "str",
    "role_template_id": "str",
    "user_id": "str",
    "user_principal_id": "str",
    "group_id": "str",
    "group_principal_id": "str",
    "namespace_id": "str",
    "service_account": "str",
    # logging_backups
    "enable_json_parsing": "bool",
    "include_system_component": "bool",
    "output_flush_interval": "int",
    "manual": "bool",
    "filename": "str",
}

QP_KWARGS: Mapping[str, str] = {
    # Steve / k8s-proxy
    "limit": "limit",
    "label_selector": "label_selector",
    "field_selector": "field_selector",
    "continue_token": "continue_token",
    # Norman: kwarg names match the descriptor names; the pack-local builder
    # is responsible for mapping kwargs to HTTP query param names (e.g.
    # `sort_by` → `sort`, `enabled` → `value`).
    "state": "state",
    "source": "source",
    "customized": "customized",
    "enabled": "enabled",
    "sort_by": "sort_by",
    "reverse": "reverse",
    "marker": "marker",
    "cluster_id": "cluster_id",
    "me": "me",
    "severity": "severity",
    "name": "name",
    "provider_type": "provider_type",
    "access_mode": "access_mode",
    # apps_catalogs
    "kind": "kind",
    "helm_version": "helm_version",
    "catalog_id": "catalog_id",
    "category": "category",
    "project_id": "project_id",
    "external_id": "external_id",
    "version": "version",
    "version_name": "version_name",
    # rbac
    "builtin": "builtin",
    "new_user_default": "new_user_default",
    "context": "context",
    "administrative": "administrative",
    "cluster_creator_default": "cluster_creator_default",
    "project_creator_default": "project_creator_default",
    "external": "external",
    "hidden": "hidden",
    "locked": "locked",
    "global_role_id": "global_role_id",
    "role_template_id": "role_template_id",
    "user_id": "user_id",
    "user_principal_id": "user_principal_id",
    "group_id": "group_id",
    "group_principal_id": "group_principal_id",
    "namespace_id": "namespace_id",
    "service_account": "service_account",
    # logging_backups
    "enable_json_parsing": "enable_json_parsing",
    "include_system_component": "include_system_component",
    "output_flush_interval": "output_flush_interval",
    "manual": "manual",
    "filename": "filename",
}


def qp_type(name: str) -> str:
    """Return the Python type for a Steve query-param kwarg."""

    return QP_TYPES[name]


def qp_kwarg(name: str) -> str:
    """Return the build_steve_list_query_params kwarg name for a query param."""

    return QP_KWARGS[name]


def split_model_path(full_path: str) -> tuple[str, str]:
    """Split `pkg.subpkg.ClassName` → (`pkg.subpkg`, `ClassName`)."""

    module, _, name = full_path.rpartition(".")
    return module, name


@dataclass(frozen=True)
class ModuleContext:
    """Template context for one descriptor's `_generated_<id>.py` file."""

    descriptor: Descriptor
    list_model_name: str
    detail_model_name: str

    def as_jinja_context(self) -> dict[str, object]:
        """Convert to a kwargs dict for Jinja's `template.render(**ctx)`."""

        descriptor = self.descriptor
        if descriptor.transport == "k8s-proxy":
            fetch_docstring_phrase = (
                f"{descriptor.display_name_plural} through Rancher's raw Kubernetes proxy"
            )
        elif descriptor.transport == "norman":
            fetch_docstring_phrase = f"the Rancher {descriptor.display_name_plural} collection"
        elif descriptor.namespaced:
            fetch_docstring_phrase = (
                f"the {descriptor.display_name_plural} collection for one namespace"
            )
        else:
            fetch_docstring_phrase = f"the {descriptor.display_name_plural} collection"
        return {
            "id": descriptor.id,
            "pack": descriptor.pack,
            "display_name_singular": descriptor.display_name_singular,
            "display_name_plural": descriptor.display_name_plural,
            "plane": descriptor.plane,
            "transport": descriptor.transport,
            "namespaced": descriptor.namespaced,
            "cluster_id_required": descriptor.cluster_id_required,
            "pagination": descriptor.pagination,
            "list_path": descriptor.list_path,
            "detail_path": descriptor.detail_path,
            "path_helper": descriptor.path_helper,
            "list_model_name": self.list_model_name,
            "detail_model_name": self.detail_model_name,
            "shared_imports": sorted(
                set(descriptor.shared_imports)
                | (
                    {descriptor.query_builder_function}
                    if descriptor.query_builder_in_shared
                    else set()
                )
            ),
            "support_value_imports": sorted(descriptor.support_value_imports),
            "summary_function": descriptor.summary_function,
            "query_builder_function": descriptor.query_builder_function,
            "query_builder_in_shared": descriptor.query_builder_in_shared,
            "operations": descriptor.operations,
            "list": descriptor.list_,
            "get": descriptor.get,
            "tools": descriptor.tools,
            "fetch_docstring_phrase": fetch_docstring_phrase,
        }


@dataclass(frozen=True)
class RegistrationEntry:
    """One `mcp.tool(...)` line in the pack register function."""

    tool_name: str
    annotation: str
    callable: str


@dataclass(frozen=True)
class ImportEntry:
    """One `from ... import (...)` block in the pack `__init__.py`."""

    id: str
    names: list[str]


def _empty_descriptor_list() -> list[Descriptor]:
    return []


@dataclass(frozen=True)
class PackContext:
    """Template context for a pack's `__init__.py`."""

    pack: PackDescriptor
    descriptors: list[Descriptor] = field(default_factory=_empty_descriptor_list)

    def as_jinja_context(self) -> dict[str, object]:
        """Convert to a kwargs dict for Jinja's `template.render(**ctx)`."""

        annotation_imports = sorted(
            {
                meta.annotation_set
                for descriptor in self.descriptors
                for meta in _tool_metas(descriptor)
            }
        )
        return {
            "pack": self.pack,
            "import_blocks": [self._import_entry(d) for d in self.descriptors],
            "all_public_names": sorted(
                name
                for descriptor in self.descriptors
                for name in _public_names(descriptor)
                if not name.endswith("_tool")
            ),
            "annotation_imports": ", ".join(annotation_imports),
            "registrations": [
                reg for descriptor in self.descriptors for reg in _registrations(descriptor)
            ],
        }

    @staticmethod
    def _import_entry(descriptor: Descriptor) -> ImportEntry:
        return ImportEntry(id=descriptor.id, names=sorted(_public_names(descriptor)))


def _public_names(descriptor: Descriptor) -> list[str]:
    """Names exported from one descriptor's generated module."""

    plural = descriptor.display_name_plural
    singular = descriptor.display_name_singular
    names: list[str] = []
    if "list" in descriptor.operations:
        names.extend(
            [
                f"rancher_{plural}_list",
                f"rancher_{plural}_list_tool",
            ]
        )
    if "get" in descriptor.operations:
        names.extend(
            [
                f"rancher_{singular}_get",
                f"rancher_{singular}_get_tool",
            ]
        )
    return names


def _tool_metas(descriptor: Descriptor) -> Iterator[ToolMeta]:
    """Yield each operation's tool metadata for the descriptor."""

    if descriptor.tools.list_ is not None:
        yield descriptor.tools.list_
    if descriptor.tools.get is not None:
        yield descriptor.tools.get


def _registrations(descriptor: Descriptor) -> list[RegistrationEntry]:
    """Build register-function entries for one descriptor."""

    plural = descriptor.display_name_plural
    singular = descriptor.display_name_singular
    entries: list[RegistrationEntry] = []
    if descriptor.tools.list_ is not None:
        entries.append(
            RegistrationEntry(
                tool_name=descriptor.tools.list_.name,
                annotation=descriptor.tools.list_.annotation_set,
                callable=f"rancher_{plural}_list_tool",
            )
        )
    if descriptor.tools.get is not None:
        entries.append(
            RegistrationEntry(
                tool_name=descriptor.tools.get.name,
                annotation=descriptor.tools.get.annotation_set,
                callable=f"rancher_{singular}_get_tool",
            )
        )
    return entries


def build_module_context(descriptor: Descriptor) -> ModuleContext:
    """Resolve the template context for one descriptor module."""

    _, list_model_name = split_model_path(descriptor.list_response_model)
    _, detail_model_name = split_model_path(descriptor.detail_response_model)
    return ModuleContext(
        descriptor=descriptor,
        list_model_name=list_model_name,
        detail_model_name=detail_model_name,
    )


def build_pack_contexts(
    packs: Mapping[str, PackDescriptor],
    descriptors: list[Descriptor],
) -> list[PackContext]:
    """Group descriptors by pack and pair with pack metadata."""

    grouped: dict[str, list[Descriptor]] = {}
    for descriptor in descriptors:
        grouped.setdefault(descriptor.pack, []).append(descriptor)

    contexts: list[PackContext] = []
    for pack_id, pack_descriptors in grouped.items():
        if pack_id not in packs:
            raise ValueError(
                f"descriptors reference pack {pack_id!r} but no _packs/{pack_id}.yml exists"
            )
        contexts.append(
            PackContext(
                pack=packs[pack_id],
                descriptors=sorted(pack_descriptors, key=lambda d: d.id),
            )
        )
    return sorted(contexts, key=lambda ctx: ctx.pack.id)
