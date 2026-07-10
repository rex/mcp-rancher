"""YAML loaders for per-resource and pack-level descriptor files."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml

from .models import Descriptor, PackDescriptor


def load_descriptor(path: Path) -> Descriptor:
    """Load and validate one per-resource descriptor file."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"{path}: top-level YAML must be a mapping")
    return Descriptor.model_validate(cast(Mapping[str, object], raw))


def load_pack_descriptor(path: Path) -> PackDescriptor:
    """Load and validate one pack-level metadata file."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"{path}: top-level YAML must be a mapping")
    return PackDescriptor.model_validate(cast(Mapping[str, object], raw))


def load_all_descriptors(directory: Path) -> list[Descriptor]:
    """Load every per-resource descriptor under the given directory."""

    descriptor_files = [p for p in directory.glob("*.yml") if not p.name.startswith("_")]
    return sorted(
        (load_descriptor(p) for p in descriptor_files),
        key=lambda d: (d.pack, d.id),
    )


def load_all_pack_descriptors(directory: Path) -> dict[str, PackDescriptor]:
    """Load every pack-level metadata file under directory/_packs/."""

    packs_dir = directory / "_packs"
    if not packs_dir.is_dir():
        return {}
    return {pack.id: pack for pack in (load_pack_descriptor(p) for p in packs_dir.glob("*.yml"))}
