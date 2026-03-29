"""Shared model helpers for curated app catalog tools."""

from rancher_mcp.models.clusters_nodes import RancherCondition


def empty_conditions() -> list[RancherCondition]:
    """Return a typed empty condition list for default factories."""

    return []


def empty_strings() -> list[str]:
    """Return a typed empty string list for default factories."""

    return []


def empty_objects() -> list[dict[str, object]]:
    """Return a typed empty object list for default factories."""

    return []


__all__ = [
    "RancherCondition",
    "empty_conditions",
    "empty_objects",
    "empty_strings",
]
