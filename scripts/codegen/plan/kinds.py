"""Resource-kind registry plan: collects every descriptor with `generic_kind`
set into one flat list ready for the `resource_kinds.py.j2` template.

Kept in its own module (rather than folded into `module.py`/`pack.py`)
because it is cross-pack: unlike a `ModuleContext` (one descriptor -> one
pack file), this spans every pack that has at least one `generic_kind`
descriptor and produces exactly one generated file,
`tools/resource_kinds/_generated_kinds.py` — the closed `resource_kind`
enums and routing registry behind the three collapsed generic mutation
tools (`rancher_resource_set_labels` / `_set_annotations` / `_delete`).
"""

from __future__ import annotations

from dataclasses import dataclass

from scripts.codegen.descriptor import Descriptor


@dataclass(frozen=True)
class KindEntry:
    """One resource kind's routing info for the generic collapsed tools."""

    descriptor_id: str
    """Descriptor id. Also the generated per-kind path-function suffix
    (``_detail_path_<descriptor_id>``) — unique by construction (it is the
    catalog YAML filename stem)."""

    kind: str
    """The ``resource_kind`` enum value. Always ``display_name_singular`` —
    matches the pre-collapse per-resource tools'
    ``RancherCuratedDeleteResult.resource_kind`` convention."""

    namespaced: bool
    plane: str
    transport: str
    get_tool: str
    list_tool: str
    supports_labels: bool
    supports_annotations: bool
    supports_delete: bool

    # Path building — exactly one family is populated, matching transport.
    steve_template: str | None
    """Normalized detail-path template using only ``{namespace}``/``{name}``
    placeholders (set when ``transport == "steve"``)."""
    path_helper_module: str | None
    path_helper_module_alias: str | None
    path_helper_detail_function: str | None
    path_helper_resource_kind: str | None
    """The literal resource-kind string passed to the path helper, for
    helpers not pre-bound to one resource type. ``None`` either when the
    helper IS pre-bound (e.g. ``storage_class_resource_path``) or when
    ``transport == "steve"``."""


def _normalize_steve_template(descriptor: Descriptor) -> str:
    """Rewrite ``detail_path``'s resource-name placeholder to the generic
    ``{name}``, leaving a namespace placeholder (when present) alone.

    E.g. ``/pods/{namespace}/{pod_name}`` (``get.arg_name="pod_name"``)
    becomes ``/pods/{namespace}/{name}``. For a kind whose OWN name IS the
    namespace segment (``namespaces``: ``arg_name="namespace"``,
    ``detail_path="/namespaces/{namespace}"``), the single placeholder is
    the arg-name one, so it becomes ``/namespaces/{name}`` with no separate
    namespace placeholder left — correct, since that kind is
    ``namespaced: false`` (a namespace names itself, it does not live
    inside one).
    """

    if descriptor.get is None:
        # Unreachable given Descriptor._check_consistency (generic_kind
        # requires 'get' in operations) — see build_kind_entries's matching
        # note; cheap insurance against that invariant changing silently.
        raise ValueError(f"{descriptor.id}: generic_kind requires get")
    arg_placeholder = "{" + descriptor.get.arg_name + "}"
    return descriptor.detail_path.replace(arg_placeholder, "{name}")


def _module_alias(module: str) -> str:
    """Deterministic, collision-free import alias for a path-helper module.

    Derived from the module's PACK segment (``...tools.<pack>.paths`` ->
    ``_paths_<pack>``), not the trailing function name: two different packs'
    ``paths.py`` modules can and do export a same-named function (e.g.
    ``core_v1_resource_path`` in both ``config_secrets.paths`` and
    ``governance.paths``) — a flat ``from mod import func`` per function
    would silently let the second import shadow the first. Aliasing by
    module (one pack has exactly one ``paths.py``) sidesteps that
    regardless of which function names collide, now or in the future.
    """

    pack_segment = module.rsplit(".", 2)[-2]
    return f"_paths_{pack_segment}"


def build_kind_entries(descriptors: list[Descriptor]) -> list[KindEntry]:
    """Every `KindEntry` for descriptors that opt into the generic collapse,
    sorted by kind name for deterministic, reviewable codegen output."""

    entries: list[KindEntry] = []
    seen_kinds: set[str] = set()
    for d in descriptors:
        if d.generic_kind is None:
            continue
        if d.get is None or d.tools.get is None or d.tools.list_ is None:
            # Unreachable given Descriptor._check_consistency (generic_kind
            # requires 'get' in operations, which itself requires tools.get;
            # 'list' + tools.list are separately required whenever list_ is
            # used downstream) — an explicit raise here is cheap insurance
            # against that invariant changing without this module noticing.
            raise ValueError(f"{d.id}: generic_kind requires get + tools.get + tools.list")
        kind = d.display_name_singular
        if kind in seen_kinds:
            raise ValueError(
                f"duplicate generic_kind resource_kind value {kind!r} "
                f"(descriptor {d.id!r}) — display_name_singular must be "
                f"unique across every generic_kind descriptor"
            )
        seen_kinds.add(kind)
        if d.transport == "steve":
            steve_template = _normalize_steve_template(d)
            ph_module = ph_alias = ph_detail_fn = ph_resource_kind = None
        elif d.transport == "k8s-proxy":
            if d.path_helper is None:
                # Unreachable given Descriptor._check_consistency
                # (transport=k8s-proxy requires path_helper) — see the note
                # on the equivalent check above.
                raise ValueError(f"{d.id}: transport=k8s-proxy but path_helper is None")
            steve_template = None
            ph_module = d.path_helper.module
            ph_alias = _module_alias(ph_module)
            ph_detail_fn = d.path_helper.detail_function
            ph_resource_kind = d.path_helper.resource_kind
        else:
            raise ValueError(
                f"{d.id}: generic_kind supports transport steve or k8s-proxy only "
                f"(routing to the raw Norman /v3 plane has no descriptor here yet); "
                f"got transport={d.transport!r}"
            )
        entries.append(
            KindEntry(
                descriptor_id=d.id,
                kind=d.display_name_singular,
                namespaced=d.namespaced,
                plane=d.plane,
                transport=d.transport,
                get_tool=d.tools.get.name,
                list_tool=d.tools.list_.name,
                supports_labels=d.generic_kind.labels,
                supports_annotations=d.generic_kind.annotations,
                supports_delete=d.generic_kind.delete,
                steve_template=steve_template,
                path_helper_module=ph_module,
                path_helper_module_alias=ph_alias,
                path_helper_detail_function=ph_detail_fn,
                path_helper_resource_kind=ph_resource_kind,
            )
        )
    return sorted(entries, key=lambda e: e.kind)


@dataclass(frozen=True)
class KindRegistryContext:
    """Template context for `resource_kinds.py.j2`."""

    entries: list[KindEntry]
    imports: list[tuple[str, str]]
    """Sorted, de-duplicated ``(module, alias)`` pairs to import once."""

    def as_jinja_context(self) -> dict[str, object]:
        return {
            "entries": self.entries,
            "imports": self.imports,
            "labelable_kinds": sorted(e.kind for e in self.entries if e.supports_labels),
            "annotatable_kinds": sorted(e.kind for e in self.entries if e.supports_annotations),
            "deletable_kinds": sorted(e.kind for e in self.entries if e.supports_delete),
        }


def build_kind_registry_context(descriptors: list[Descriptor]) -> KindRegistryContext:
    """Resolve the full template context for the generated kind registry."""

    entries = build_kind_entries(descriptors)
    imports = sorted(
        {
            (e.path_helper_module, e.path_helper_module_alias)
            for e in entries
            if e.path_helper_module is not None and e.path_helper_module_alias is not None
        }
    )
    return KindRegistryContext(entries=entries, imports=imports)
