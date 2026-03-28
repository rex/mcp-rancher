"""Shared low-level normalization helpers for generic resources."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast


def mapping_value(payload: object) -> Mapping[str, object] | None:
    """Return a typed mapping when the payload is mapping-like."""

    if not isinstance(payload, Mapping):
        return None
    return cast(Mapping[str, object], payload)


def mapping_keys(payload: object) -> list[str]:
    """Return sorted keys from a mapping-like payload."""

    mapping = mapping_value(payload)
    if mapping is None:
        return []
    return sorted(mapping.keys())


def mapping_list(payload: object) -> list[Mapping[str, object]]:
    """Return only mapping entries from a list-like payload."""

    if not isinstance(payload, list):
        return []
    items = cast(list[object], payload)
    return [mapping for item in items if (mapping := mapping_value(item)) is not None]
