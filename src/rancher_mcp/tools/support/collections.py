"""Shared collection helpers for curated tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast


def object_items(
    payload: Mapping[str, object],
    *,
    field: str,
) -> list[dict[str, object]]:
    """Extract typed object items from one list field."""

    raw_items = payload.get(field)
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, object]] = []
    for item in cast(list[object], raw_items):
        if isinstance(item, dict):
            items.append(cast(dict[str, object], item))
    return items
