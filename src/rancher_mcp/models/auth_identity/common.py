"""Shared helpers for curated auth and identity models."""

from rancher_mcp.models.clusters_nodes import RancherCondition


def empty_conditions() -> list[RancherCondition]:
    """Return a typed empty condition list for default factories."""

    return []


def empty_strings() -> list[str]:
    """Return a typed empty string list for default factories."""

    return []


__all__ = [
    "RancherCondition",
    "empty_conditions",
    "empty_strings",
]
