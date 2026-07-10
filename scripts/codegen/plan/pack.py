"""Per-pack template context and its build helpers.

`PackContext` carries the sorted import blocks, public-name exports,
annotation imports, and register entries the pack `__init__.py` template
needs; `build_pack_contexts` groups descriptors by pack and pairs each
with its pack metadata.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field

from scripts.codegen.descriptor import Descriptor, PackDescriptor, ToolMeta


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
    if "create" in descriptor.operations:
        names.extend(
            [
                f"rancher_{singular}_create",
                f"rancher_{singular}_create_tool",
            ]
        )
    if "apply" in descriptor.operations:
        names.extend(
            [
                f"rancher_{singular}_apply",
                f"rancher_{singular}_apply_tool",
            ]
        )
    if "delete" in descriptor.operations:
        names.extend(
            [
                f"rancher_{singular}_delete",
                f"rancher_{singular}_delete_tool",
            ]
        )
    if "patch" in descriptor.operations:
        for patch in descriptor.patches:
            names.extend(
                [
                    f"rancher_{singular}_{patch.verb}",
                    f"rancher_{singular}_{patch.verb}_tool",
                ]
            )
    return names


def _tool_metas(descriptor: Descriptor) -> Iterator[ToolMeta]:
    """Yield each operation's tool metadata for the descriptor."""

    if descriptor.tools.list_ is not None:
        yield descriptor.tools.list_
    if descriptor.tools.get is not None:
        yield descriptor.tools.get
    if descriptor.tools.create is not None:
        yield descriptor.tools.create
    if descriptor.tools.apply is not None:
        yield descriptor.tools.apply
    if descriptor.tools.delete is not None:
        yield descriptor.tools.delete
    yield from descriptor.tools.patches


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
    if descriptor.tools.create is not None:
        entries.append(
            RegistrationEntry(
                tool_name=descriptor.tools.create.name,
                annotation=descriptor.tools.create.annotation_set,
                callable=f"rancher_{singular}_create_tool",
            )
        )
    if descriptor.tools.apply is not None:
        entries.append(
            RegistrationEntry(
                tool_name=descriptor.tools.apply.name,
                annotation=descriptor.tools.apply.annotation_set,
                callable=f"rancher_{singular}_apply_tool",
            )
        )
    if descriptor.tools.delete is not None:
        entries.append(
            RegistrationEntry(
                tool_name=descriptor.tools.delete.name,
                annotation=descriptor.tools.delete.annotation_set,
                callable=f"rancher_{singular}_delete_tool",
            )
        )
    for index, tool_meta in enumerate(descriptor.tools.patches):
        verb = descriptor.patches[index].verb
        entries.append(
            RegistrationEntry(
                tool_name=tool_meta.name,
                annotation=tool_meta.annotation_set,
                callable=f"rancher_{singular}_{verb}_tool",
            )
        )
    return entries


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
