"""Capability catalog loading."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from rancher_mcp.models.discovery import CapabilityCatalog


def load_capability_catalog(path: Path) -> CapabilityCatalog:
    """Load the capability catalog from YAML."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Capability catalog at {path} did not decode to an object")
    return CapabilityCatalog.model_validate(raw)


@lru_cache(maxsize=1)
def get_capability_catalog(path_str: str) -> CapabilityCatalog:
    """Load and cache the capability catalog for the provided path."""

    return load_capability_catalog(Path(path_str))


def clear_capability_catalog_cache() -> None:
    """Clear the cached capability catalog."""

    get_capability_catalog.cache_clear()
